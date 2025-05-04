// rbtree.c
#include "rbtree.h"
#include <stddef.h>

#define INLINE    inline __attribute__((always_inline))

static INLINE rb_node_t *rb_grandparent(rb_node_t *n) {
    return n->parent ? n->parent->parent : NULL;
}
static INLINE rb_node_t *rb_uncle(rb_node_t *n) {
    rb_node_t *g = rb_grandparent(n);
    if (!g) return NULL;
    return (n->parent == g->left) ? g->right : g->left;
}

// Left‐rotate at node n
static INLINE void rb_rotate_left(rb_node_t *n, rb_root_t *root) {
    rb_node_t *r = n->right;
    rb_node_t *p = n->parent;

    n->right = r->left;
    if (r->left) r->left->parent = n;
    r->left = n;
    n->parent = r;

    // fix parent link
    r->parent = p;
    if (!p)           root->root = r;
    else if (p->left == n)  p->left  = r;
    else                     p->right = r;
}

// Right‐rotate at node n
static INLINE void rb_rotate_right(rb_node_t *n, rb_root_t *root) {
    rb_node_t *l = n->left;
    rb_node_t *p = n->parent;

    n->left = l->right;
    if (l->right) l->right->parent = n;
    l->right = n;
    n->parent = l;

    // fix parent link
    l->parent = p;
    if (!p)           root->root = l;
    else if (p->left == n)  p->left  = l;
    else                     p->right = l;
}

// Public: insert‐fixup
INLINE void rb_insert_color(rb_node_t *n, rb_root_t *root) {
    // standard RB-insert fixup from CLRS
    while (n != root->root && n->parent->color == RED) {
        rb_node_t *u = rb_uncle(n);
        rb_node_t *g = rb_grandparent(n);
        if (u && u->color == RED) {
            // case 1
            n->parent->color = BLACK;
            u->color         = BLACK;
            g->color         = RED;
            n = g;
        } else {
            if (n->parent == g->left) {
                if (n == n->parent->right) {
                    // case 2
                    n = n->parent;
                    rb_rotate_left(n, root);
                }
                // case 3
                n->parent->color = BLACK;
                g->color         = RED;
                rb_rotate_right(g, root);
            } else {
                if (n == n->parent->left) {
                    // mirror case 2
                    n = n->parent;
                    rb_rotate_right(n, root);
                }
                // mirror case 3
                n->parent->color = BLACK;
                g->color         = RED;
                rb_rotate_left(g, root);
            }
        }
    }
    root->root->color = BLACK;
}

// Public: find the node with largest key ≤ given key
INLINE rb_node_t *rb_search_leq(rb_root_t *root, unsigned long key) {
    rb_node_t *node = root->root;
    rb_node_t *best = NULL;
    while (node) {
        if (node->key <= key) {
            best = node;
            node = node->right;
        } else {
            node = node->left;
        }
    }
    return best;
}
