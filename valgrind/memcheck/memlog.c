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
#define MAX_LOG_ENTRIES 3000000
#define PAGE_SIZE 4096
#define MIN_BLOCK_SIZE 1*PAGE_SIZE // TODO: this should be a tool's parameter

typedef enum {
   LOG_STORE,
   LOG_ALLOC,
   LOG_FREE
} LogEventType;

typedef struct {
   LogEventType  type;
   Addr          addr;
   HWord         value;      // For LOG_STORE
   SizeT         size;       // For LOG_ALLOC, LOG_FREE
   ExeContext*   where;      // For LOG_ALLOC, LOG_FREE
} LogEntry;

static LogEntry log_buffer[MAX_LOG_ENTRIES];
static Int log_count = 0;
static rb_root_t blocks_tree = RB_ROOT;

INLINE void memlog_init(void) 
{
}

static INLINE void flush_log_buffer(void)
{
   for (Int i = 0; i < log_count; i++) {
      LogEntry* entry = &log_buffer[i];
      
      switch (entry->type) {
      case LOG_STORE:
         VG_(printf)("0x%lx 0x%lx\n", entry->addr, entry->value);
         break;
      
      case LOG_ALLOC:
         VG_(printf)("===ALLOC START===\n");
         VG_(printf)("Start 0x%lx, size %ld\n", entry->addr, entry->size);
         
         if (entry->where) {
            VG_(pp_ExeContext)(entry->where);
         } else {
            VG_(printf)("(No allocation stack trace available)\n");
         }
         
         VG_(printf)("===ALLOC END===\n");
         break;
      
      case LOG_FREE:
         VG_(printf)("===FREE START===\n");
         VG_(printf)("Start 0x%lx, size %ld\n", entry->addr, entry->size);
         
         if (entry->where) {
            VG_(pp_ExeContext)(entry->where);
         } else {
            VG_(printf)("(No free stack trace available)\n");
         }
         
         VG_(printf)("===FREE END===\n");
         break;
      }
   }
   log_count = 0;
}

static INLINE void add_to_buffer(LogEventType type, Addr addr, HWord value, SizeT size, ExeContext* where)
{
   log_buffer[log_count].type = type;
   log_buffer[log_count].addr = addr;
   if (type == LOG_STORE) {
      log_buffer[log_count].value = value;
   } else {
      log_buffer[log_count].size = size;
      log_buffer[log_count].where = where;
   }
   
   log_count++;
   if (log_count >= MAX_LOG_ENTRIES) {
      flush_log_buffer();
   }
}

static INLINE void print(Addr addr, HWord value)
{
   add_to_buffer(LOG_STORE, addr, value, 0, NULL);
}

static INLINE void insert_block_rb(MC_Chunk* mc) {
   /* ---- step 0: create the rb_node that will carry the block ---- */
   rb_node_t *n = VG_(malloc)("blocks.rbnode", sizeof(*n));
   *n = (rb_node_t){
      .parent = NULL, .left = NULL, .right = NULL,
      .color  = RED,
      .key    = mc->data,
      .data   = mc
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
         VG_(free)(n); // TODO: do not call malloc if we are not going to use it
         return;
      }
   }

   /* ---- step 2: hook it in and rebalance ---- */
   rb_link_node(n, parent, link);       /* fixes child pointer and n->parent */
   rb_insert_color(n, &blocks_tree);    /* applies RB‑tree fix‑ups          */
}

static INLINE Bool is_tracked(Addr addr) {
   rb_node_t *n = rb_search_leq(&blocks_tree, (unsigned long)addr);
   if (!n) return False;

   MC_Chunk *cand = (MC_Chunk*)n->data;
   return (addr <= cand->data + cand->szB) ? cand : False;
}

static INLINE void log_store(Addr addr, HWord value) {
    if (is_tracked(addr)) {
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
            // TODO: add support for D32 and D64
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

INLINE void memlog_handle_new_block(MC_Chunk* mc) {
   if (mc->szB < MIN_BLOCK_SIZE) return;

   ExeContext* where = MC_(allocated_at)(mc);
   add_to_buffer(LOG_ALLOC, mc->data, 0, mc->szB, where);

   insert_block_rb(mc);
}

INLINE void memlog_handle_free_block(MC_Chunk* mc) {
   if (mc->szB < MIN_BLOCK_SIZE) return;

   ExeContext* where = MC_(freed_at)(mc);
   add_to_buffer(LOG_FREE, mc->data, 0, mc->szB, where);
   
   rb_delete(&blocks_tree, mc->data);
}