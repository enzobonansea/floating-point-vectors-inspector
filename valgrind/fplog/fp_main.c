#include "pub_tool_basics.h"
#include "pub_tool_tooliface.h"
#include "pub_tool_mallocfree.h"
#include "pub_tool_options.h"
#include "pub_tool_replacemalloc.h"
#include "pub_tool_libcbase.h"    // For VG_(strlen) etc
#include "pub_tool_libcfile.h"    // For VG_(open) etc
#include "pub_tool_libcprint.h"   // For VG_(message)
#include "pub_tool_libcassert.h"

// File descriptor for logging
static Int log_fd = -1;

// Helper to determine if an allocation might hold floating-point numbers
static Bool is_fp_array(SizeT size) {
    VG_(message)(Vg_UserMsg, "-> is_fp_array checking size: %lu\n", (ULong)size);
    Bool result = size % sizeof(double) == 0 || size % sizeof(float) == 0;
    VG_(message)(Vg_UserMsg, "   result: %d\n", result);
    return result;
}
// Custom logging function to replace fprintf
static void log_message(const HChar* format, ...) 
{
    VG_(message)(Vg_UserMsg, "-> log_message\n");

    va_list vargs;
    HChar buf[1024];
    Int n;

    if (log_fd == -1) return;

    va_start(vargs, format);
    n = VG_(vsnprintf)(buf, sizeof(buf), format, vargs);
    va_end(vargs);

    if (n > 0) {
        VG_(write)(log_fd, buf, n);
    }
}

// Function to dump floating-point values
static void dump_fp_values(void* addr, SizeT size) {
    VG_(message)(Vg_UserMsg, "-> dump_fp_values called for addr %p, size %lu\n", addr, (ULong)size);

    if (log_fd == -1) {
        VG_(message)(Vg_UserMsg, "Log file not open in dump_fp_values!\n");
        return;
    }

    SizeT count = size / sizeof(double);
    double* data = (double*)addr;

    log_message("Allocated FP array at %p with %lu elements:\n", addr, (ULong)count);
    VG_(message)(Vg_UserMsg, "Wrote header to log file\n");

    for (SizeT i = 0; i < count; i++) {
        log_message("  [%lu] = %f\n", (ULong)i, data[i]);
    }
    VG_(message)(Vg_UserMsg, "Finished writing values to log file\n");
}

// Regular malloc
static void* fp_malloc(ThreadId tid, SizeT size) {
    VG_(message)(Vg_UserMsg, "-> fp_malloc\n");

    void* addr = VG_(malloc)("fp.malloc", size);
    if (is_fp_array(size)) {
        dump_fp_values(addr, size);
    }
    return addr;
}

// C++ new operator
static void* fp___builtin_new(ThreadId tid, SizeT size) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_new\n");

    void* addr = VG_(malloc)("fp.new", size);
    if (is_fp_array(size)) {
        dump_fp_values(addr, size);
    }
    return addr;
}

// C++ aligned new operator
static void* fp___builtin_new_aligned(ThreadId tid, SizeT size, SizeT align, SizeT orig_align) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_new_aligned\n");

   void* addr = VG_(cli_malloc)(align, size);
   if (!addr) return NULL;

   if (is_fp_array(size)) dump_fp_values(addr, size);

   return addr;
}

// C++ vector new operator
static void* fp___builtin_vec_new(ThreadId tid, SizeT size) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_vec_new\n");

    void* addr = VG_(malloc)("fp.vec.new", size);
    if (is_fp_array(size)) {
        dump_fp_values(addr, size);
    }
    return addr;
}

// C++ vector aligned new operator
static void* fp___builtin_vec_new_aligned(ThreadId tid, SizeT size, SizeT align, SizeT orig_align) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_vec_new_aligned\n");

   void* addr = VG_(cli_malloc)(align, size);
   if (!addr) return NULL;
   
   if (is_fp_array(size)) dump_fp_values(addr, size);

   return addr;
}

// Aligned memory allocation
static void* fp_memalign(ThreadId tid, SizeT align, SizeT orig_align, SizeT size) {
    VG_(message)(Vg_UserMsg, "-> fp_memalign\n");

   void* addr = VG_(cli_malloc)(align, size);
   if (!addr) return NULL;
   
   if (is_fp_array(size)) dump_fp_values(addr, size);

   return addr;
}

// Calloc
static void* fp_calloc(ThreadId tid, SizeT nmemb, SizeT size) {
    VG_(message)(Vg_UserMsg, "-> fp_calloc\n");

    void* addr = VG_(calloc)("fp.calloc", nmemb, size);
    if (is_fp_array(nmemb * size)) {
        dump_fp_values(addr, nmemb * size);
    }
    return addr;
}

// Free functions remain unchanged
static void fp_free(ThreadId tid, void* p) {
    VG_(message)(Vg_UserMsg, "-> fp_free\n");

    VG_(free)(p);
}

static void fp___builtin_delete(ThreadId tid, void* p) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_delete\n");

    VG_(free)(p);
}

static void fp___builtin_delete_aligned(ThreadId tid, void* p, SizeT align) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_delete_aligned\n");

    VG_(free)(p);
}

static void fp___builtin_vec_delete(ThreadId tid, void* p) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_vec_delete\n");

    VG_(free)(p);
}

static void fp___builtin_vec_delete_aligned(ThreadId tid, void* p, SizeT align) {
    VG_(message)(Vg_UserMsg, "-> fp___builtin_vec_delete_aligned\n");

    VG_(free)(p);
}

// Realloc
static void* fp_realloc(ThreadId tid, void* p, SizeT size) {
    VG_(message)(Vg_UserMsg, "-> fp_realloc\n");

    void* new_addr = VG_(realloc)("fp.realloc", p, size);
    if (is_fp_array(size)) {
        dump_fp_values(new_addr, size);
    }
    return new_addr;
}

// Get usable size of allocation
static SizeT fp_malloc_usable_size(ThreadId tid, void* p) {
    VG_(message)(Vg_UserMsg, "-> fp_malloc_usable_size\n");

    return VG_(cli_malloc_usable_size)(p); 
}


/********** VALGRIND INTERFACE **********/
static void fp_fini(Int exitcode) {
    if (log_fd >= 0) {
        VG_(close)(log_fd);
        log_fd = -1;
    }
}

static IRSB* fp_instrument(VgCallbackClosure* closure,
                           IRSB* bb,
                           const VexGuestLayout* layout,
                           const VexGuestExtents* vge,
                           const VexArchInfo* archinfo_host,
                           IRType gWordTy, IRType hWordTy) {
    return bb;
}

static void fp_post_clo_init(void) {}

static void fp_pre_clo_init(void) {
    VG_(details_name)("Floating points logger");
    VG_(details_version)(NULL);
    VG_(details_description)("for my computer science thesis");
    VG_(details_copyright_author)("Enzo Bonansea");
    VG_(details_bug_reports_to)(VG_BUGS_TO);
    VG_(details_avg_translation_sizeB)(275);
    VG_(basic_tool_funcs)(fp_post_clo_init, fp_instrument, fp_fini);

    VG_(needs_libc_freeres)        ();
    VG_(needs_cxx_freeres)         ();
    VG_(needs_malloc_replacement)(
        fp_malloc,
        fp___builtin_new,
        fp___builtin_new_aligned,
        fp___builtin_vec_new,
        fp___builtin_vec_new_aligned,
        fp_memalign,
        fp_calloc,
        fp_free,
        fp___builtin_delete,
        fp___builtin_delete_aligned,
        fp___builtin_vec_delete,
        fp___builtin_vec_delete_aligned,
        fp_realloc,
        fp_malloc_usable_size,
        0
    );

    // Open log file early
    log_fd = VG_(fd_open)("/tmp/allocations.log", 
                         VKI_O_CREAT | VKI_O_WRONLY | VKI_O_TRUNC,
                         VKI_S_IRUSR | VKI_S_IWUSR);
    
    if (log_fd == -1) {
        VG_(message)(Vg_UserMsg, "Failed to open log file for writing\n");
    } else {
        VG_(message)(Vg_UserMsg, "Successfully opened log file with fd: %d\n", log_fd);
        VG_(write)(log_fd, "Log file initialized\n", 20);
    }

    VG_(needs_xml_output)();
    VG_(needs_core_errors)(True);
}

VG_DETERMINE_INTERFACE_VERSION(fp_pre_clo_init)