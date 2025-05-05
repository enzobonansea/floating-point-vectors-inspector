// rbtree.h
#ifndef RBTREE_H
#define RBTREE_H

#include <stddef.h>

typedef enum { RED, BLACK } rb_color_t;

typedef struct rb_node {
    struct rb_node *parent, *left, *right;
    rb_color_t      color;
    unsigned long   key;        // use `addr` or cast your Addr to ulong
    void           *data;       // store your BlockNode*
} rb_node_t;

typedef struct rb_root {
    rb_node_t *root;
} rb_root_t;

#define RB_ROOT (rb_root_t){ .root = NULL }

static inline void rb_link_node(rb_node_t *node, rb_node_t *parent, rb_node_t **linkp) {
    node->parent = parent;
    node->left   = node->right = NULL;
    *linkp = node;
}

void rb_insert_color(rb_node_t *node, rb_root_t *root);
rb_node_t *rb_search_leq(rb_root_t *root, unsigned long key);
rb_node_t *rb_delete(rb_root_t *root, unsigned long key);

#endif
