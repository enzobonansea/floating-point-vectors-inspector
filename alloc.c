#include "stdio.h"

int main() {
    int qty = 10000000;
    float* ptr_f = (float*)malloc(qty*sizeof(float));
    printf("ptr_f=%p\n", ptr_f);
    for (int i=0; i<qty; i++) *(ptr_f+i) = 0.6f;
    free(ptr_f);

    return 0;
}