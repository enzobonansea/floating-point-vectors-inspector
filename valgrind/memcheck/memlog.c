#include "pub_tool_basics.h"
#include "pub_tool_aspacemgr.h"
#include "pub_tool_poolalloc.h"
#include "pub_tool_hashtable.h"
#include "pub_tool_libcbase.h"
#include "pub_tool_libcprint.h"
#include "pub_tool_mallocfree.h"
#include "pub_tool_tooliface.h"
#include "pub_tool_threadstate.h"
#include "mc_include.h"
#include "memcheck.h"
#include "memlog.h"
#include "rbtree.h"

#define INLINE    inline __attribute__((always_inline))
#define MAX_LOG_ENTRIES 30000000
#define PAGE_SIZE 4096
#define MIN_BLOCK_SIZE 1*PAGE_SIZE // TODO: this should be a tool's parameter

typedef struct {
   Addr        addr;
   HWord       value;
} LogEntry;

typedef struct BlockNode {
   struct rb_node        rb;
   UWord                  key;
   Addr                  start;
   SizeT                 size;
   ExeContext*           allocation_site;
   struct BlockNode    * next;
} BlockNode;

static LogEntry log_buffer[MAX_LOG_ENTRIES];
static Int log_count = 0;
static VgHashTable *blocks = NULL; 
static rb_root_t blocks_tree = RB_ROOT;

INLINE void memlog_init(void) 
{
   blocks = VG_(HT_construct)("blocks");
}

static INLINE void flush_log_buffer(void)
{
   for (Int i = 0; i < log_count; i++) {
      VG_(printf)("0x%lx 0x%lx\n", log_buffer[i].addr, log_buffer[i].value);
   }
   log_count = 0;
}

static INLINE void print(Addr addr, HWord value)
{
   log_buffer[log_count].addr       = addr;
   log_buffer[log_count].value      = value;
   log_count++;
   if (log_count >= MAX_LOG_ENTRIES) {
      flush_log_buffer();
   }
}

static INLINE void insert_block_rb(BlockNode *b) {
   /* ---- step 0: create the rb_node that will carry the block ---- */
   rb_node_t *n = VG_(malloc)("blocks.rbnode", sizeof(*n));
   *n = (rb_node_t){
      .parent = NULL, .left = NULL, .right = NULL,
      .color  = RED,
      .key    = b->start,   /* <‑‑ key used for ordering      */
      .data   = b           /* <‑‑ payload: the BlockNode*    */
   };

   /* ---- step 1: ordinary ordered‑binary‑tree insertion walk ---- */
   rb_node_t **link  = &blocks_tree.root;   /* pointer to current link */
   rb_node_t  *parent = NULL;               /* parent node we land under */

   while (*link) {
      parent = *link;
      if (n->key < parent->key)
         link = &parent->left;
      else if (n->key > parent->key)
         link = &parent->right;
      else {
         /* same start address already present – nothing to do   */
         VG_(free)(n);
         return;
      }
   }

   /* ---- step 2: hook it in and rebalance ---- */
   rb_link_node(n, parent, link);       /* fixes child pointer and n->parent */
   rb_insert_color(n, &blocks_tree);    /* applies RB‑tree fix‑ups          */
}

static INLINE BlockNode* find_block(Addr addr) {
   BlockNode* exact = (BlockNode*)VG_(HT_lookup)(blocks, addr);
   if (exact) return exact;

   rb_node_t *n = rb_search_leq(&blocks_tree, (unsigned long)addr);
   if (!n) return NULL;
   BlockNode *cand = (BlockNode*)n->data;
   return (addr <= cand->start + cand->size) ? cand : NULL;
}

static INLINE BlockNode* find_or_create_block(Addr addr) {
   BlockNode* b = find_block(addr);

   if (!b) {
      BlockNode* newb = VG_(malloc)("blocks.node", sizeof(*newb));
      newb->next = NULL;
      newb->key   = addr;
      newb->start = addr;
      newb->size  = 0;
      newb->allocation_site = NULL;

      AddrInfo ai = { .tag = Addr_Undescribed };
      describe_addr(VG_(current_DiEpoch)(), addr, &ai);
      if (ai.tag == Addr_Block) {
         newb->key             = addr - ai.Addr.Block.rwoffset;
         newb->start           = newb->key;
         newb->size            = ai.Addr.Block.block_szB;
         newb->allocation_site = ai.Addr.Block.allocated_at;
      }

      VG_(HT_add_node)(blocks, newb);
      insert_block_rb(newb);

      b = newb;
   }

   return b;
}

static INLINE void log_store(Addr addr, HWord value) {
    if (find_or_create_block(addr)->size > MIN_BLOCK_SIZE) {
        print(addr, value);
    }
}

static void free_rb_tree_recursive(rb_node_t *node) {
   if (!node)
       return;
   
   free_rb_tree_recursive(node->left);
   free_rb_tree_recursive(node->right);

   VG_(free)(node);
}

static void free_rb_tree(rb_root_t *root) {
   free_rb_tree_recursive(root->root);
   root->root = NULL;
}

INLINE void memlog_fini(void) {
   flush_log_buffer();
   
    VG_(printf)("\n=== Allocation sites ===\n");
    
    VgHashNode *node;
    VG_(HT_ResetIter)(blocks);
    while ((node = VG_(HT_Next)(blocks))) {
      BlockNode* block_node = (BlockNode*)node;
      // Avoid those nodes that aren't actually a Block but they are into the hash table for 
      // reducing the quantity of calls to describe_addr in log_store an thus increase the tool's throughput
      if (block_node->allocation_site && block_node->size > MIN_BLOCK_SIZE) {
         VG_(printf)("Start 0x%lx, size %ld\n", block_node->start, block_node->size);
         VG_(pp_ExeContext)(block_node->allocation_site);
         VG_(printf)("\n");
      }
    }

    VG_(HT_destruct) (blocks, VG_(free));
    free_rb_tree(&blocks_tree);
}

static INLINE Bool is_app_code(const VexGuestExtents* vge)
{
   Bool vge_has_app_code = False;
   for (int i = 0; i < vge->n_used && !vge_has_app_code; i++) {
      Addr addr = vge->base[i];
      const NSegment* seg = VG_(am_find_nsegment)(addr);
      if (seg) {
         const HChar* filename = VG_(am_get_filename)(seg);
         vge_has_app_code = VG_(strncmp)(filename, "/usr", 4) == 0;
      }
   }

   return vge_has_app_code;
}

static INLINE void wire_log_store(IRSB* bb_out,
   IRTemp  addr_tmp,
   IRExpr* addr,
   IRTemp  data_tmp,
   IRExpr* data_widen)
{
   addStmtToIRSB(bb_out, IRStmt_WrTmp(addr_tmp, addr));
   addStmtToIRSB(bb_out, IRStmt_WrTmp(data_tmp, data_widen));
   IRDirty* dirty = unsafeIRDirty_0_N(
      0, 
      "log_store", 
      (void*)VG_(fnptr_to_fnentry)(log_store),
      mkIRExprVec_2(IRExpr_RdTmp(addr_tmp), IRExpr_RdTmp(data_tmp)));
   addStmtToIRSB(bb_out, IRStmt_Dirty(dirty));
}

static INLINE IRSB* wire_memlog(IRSB* bb_in)
{
   IRSB* bb_out = deepCopyIRSBExceptStmts(bb_in);
   IRTemp addr_tmp, data_tmp, addr_tmp1, data_tmp1, addr_tmp2, data_tmp2, addr_tmp3, data_tmp3;

   for (Int i = 0; i < bb_in->stmts_used; i++) {
      IRStmt* stmt = bb_in->stmts[i];
      if (!stmt)
         continue;

      if (stmt->tag == Ist_Store) {
         IRExpr* data       = stmt->Ist.Store.data;
         IRExpr* addr       = stmt->Ist.Store.addr;
         addr_tmp           = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp           = newIRTemp(bb_out->tyenv, Ity_I64);
         addr_tmp1          = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp1          = newIRTemp(bb_out->tyenv, Ity_I64);
         addr_tmp2          = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp2          = newIRTemp(bb_out->tyenv, Ity_I64);
         addr_tmp3          = newIRTemp(bb_out->tyenv, Ity_I64);
         data_tmp3          = newIRTemp(bb_out->tyenv, Ity_I64);
         IRType  ty         = typeOfIRExpr(bb_in->tyenv, data);
         switch (ty) {
         case Ity_I1:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_1Uto64, data));
            break;
         case Ity_I8:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_8Uto64, data));
            break;
         case Ity_I16:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_16Uto64, data));
            break;
         case Ity_I32:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_32Uto64, data));
            break;
         case Ity_I64:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, data);
            break;
         case Ity_F32:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_F32toI64U, data));
            break;
         case Ity_F64:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, data);
            break;
         case Ity_V128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_V128HIto64, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_V128to64, data));
            break;
         case Ity_I128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_128HIto64, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_128to64, data));
            break;
         case Ity_F128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_F128HItoF64, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_F128LOtoF64, data));
            break;
         case Ity_D128:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_D128HItoD64, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_D128LOtoD64, data));
            break;
         case Ity_F16:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_F16toF64, data));
            break;
         case Ity_V256:
            wire_log_store(bb_out, addr_tmp, addr, data_tmp, IRExpr_Unop(Iop_V256to64_3, data));
            wire_log_store(bb_out, addr_tmp1, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(8))), data_tmp1, IRExpr_Unop(Iop_V256to64_2, data));
            wire_log_store(bb_out, addr_tmp2, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(16))), data_tmp2, IRExpr_Unop(Iop_V256to64_1, data));
            wire_log_store(bb_out, addr_tmp3, IRExpr_Binop(Iop_Add64, addr, IRExpr_Const(IRConst_U64(24))), data_tmp3, IRExpr_Unop(Iop_V256to64_0, data));
            break;
         case Ity_D32:
         case Ity_D64:
            // TODO
            break;
         case Ity_INVALID:
            break;
         }
      }

      addStmtToIRSB(bb_out, stmt);
   }

   return bb_out;
}

INLINE IRSB* memlog_instrument(VgCallbackClosure* closure,
    IRSB* bb_in,
    const VexGuestLayout* layout,
    const VexGuestExtents* vge,
    const VexArchInfo* archinfo_host,
    IRType gWordTy,
    IRType hWordTy) {
    return is_app_code(vge) ? wire_memlog(bb_in) : bb_in;
}