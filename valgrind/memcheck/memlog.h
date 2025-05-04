#ifndef MEMLOG_H
#define MEMLOG_H

#include "pub_tool_basics.h"
#include "pub_tool_options.h"
#include "pub_tool_addrinfo.h"
#include "pub_tool_execontext.h"
#include "rbtree.h"

void  memlog_init(void);
void  memlog_fini(void);
IRSB* memlog_instrument(
    VgCallbackClosure* closure,
    IRSB* bb_in,
    const VexGuestLayout* layout,
    const VexGuestExtents* vge,
    const VexArchInfo* archinfo_host,
    IRType gWordTy,
    IRType hWordTy);

#endif
