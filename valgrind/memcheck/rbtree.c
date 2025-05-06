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

// Public: link a new node into the tree
INLINE void rb_link_node(rb_node_t *node, rb_node_t *parent, rb_node_t **linkp) {
    node->parent = parent;
    node->left   = node->right = NULL;
    *linkp = node;
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

// Function to find a node with the exact key
static INLINE rb_node_t *rb_search(rb_root_t *root, unsigned long key) {
    rb_node_t *node = root->root;
    while (node) {
        if (node->key == key)
            return node;
        else if (key < node->key)
            node = node->left;
        else
            node = node->right;
    }
    return NULL;  // Not found
}

// Find the minimum node in a subtree
static INLINE rb_node_t *rb_min(rb_node_t *node) {
    if (!node) return NULL;
    while (node->left)
        node = node->left;
    return node;
}

// Replace one node with another in the tree
static INLINE void rb_transplant(rb_root_t *root, rb_node_t *u, rb_node_t *v) {
    if (!u->parent)
        root->root = v;
    else if (u == u->parent->left)
        u->parent->left = v;
    else
        u->parent->right = v;
    if (v)
        v->parent = u->parent;
}

// Fix red-black properties after deletion
static INLINE void rb_delete_fixup(rb_root_t *root, rb_node_t *x, rb_node_t *parent) {
    rb_node_t *w;
    
    while (x != root->root && (!x || x->color == BLACK)) {
        if (!parent) break;
        
        if (x == parent->left) {
            w = parent->right;
            if (!w) break;
            
            if (w->color == RED) {
                w->color = BLACK;
                parent->color = RED;
                rb_rotate_left(parent, root);
                w = parent->right;
            }
            
            if ((!w->left || w->left->color == BLACK) && 
                (!w->right || w->right->color == BLACK)) {
                w->color = RED;
                x = parent;
                parent = parent->parent;
            } else {
                if (!w->right || w->right->color == BLACK) {
                    if (w->left)
                        w->left->color = BLACK;
                    w->color = RED;
                    rb_rotate_right(w, root);
                    w = parent->right;
                }
                
                w->color = parent->color;
                parent->color = BLACK;
                if (w->right)
                    w->right->color = BLACK;
                rb_rotate_left(parent, root);
                x = root->root;
                parent = NULL;
            }
        } else {
            w = parent->left;
            if (!w) break;
            
            if (w->color == RED) {
                w->color = BLACK;
                parent->color = RED;
                rb_rotate_right(parent, root);
                w = parent->left;
            }
            
            if ((!w->right || w->right->color == BLACK) && 
                (!w->left || w->left->color == BLACK)) {
                w->color = RED;
                x = parent;
                parent = parent->parent;
            } else {
                if (!w->left || w->left->color == BLACK) {
                    if (w->right)
                        w->right->color = BLACK;
                    w->color = RED;
                    rb_rotate_left(w, root);
                    w = parent->left;
                }
                
                w->color = parent->color;
                parent->color = BLACK;
                if (w->left)
                    w->left->color = BLACK;
                rb_rotate_right(parent, root);
                x = root->root;
                parent = NULL;
            }
        }
    }
    
    if (x)
        x->color = BLACK;
}

// Public: delete a node with the given key from the tree
// Returns the deleted node (for caller to free) or NULL if key not found
rb_node_t *rb_delete(rb_root_t *root, unsigned long key) {
    rb_node_t *z = rb_search(root, key);
    if (!z) return NULL;  // Node not found
    
    rb_node_t *y = z;
    rb_node_t *x;
    rb_node_t *x_parent;
    rb_color_t y_original_color = y->color;
    
    if (!z->left) {
        x = z->right;
        x_parent = z->parent;
        rb_transplant(root, z, z->right);
    } else if (!z->right) {
        x = z->left;
        x_parent = z->parent;
        rb_transplant(root, z, z->left);
    } else {
        y = rb_min(z->right);
        y_original_color = y->color;
        x = y->right;
        
        if (y->parent == z) {
            x_parent = y;
        } else {
            x_parent = y->parent;
            rb_transplant(root, y, y->right);
            y->right = z->right;
            y->right->parent = y;
        }
        
        rb_transplant(root, z, y);
        y->left = z->left;
        y->left->parent = y;
        y->color = z->color;
    }
    
    if (y_original_color == BLACK)
        rb_delete_fixup(root, x, x_parent);
    
    return z;  // Return the deleted node so the caller can free it
}
