#include <stdio.h>

int main() {
    int qty = 1000;
    float* f = (float*)malloc(qty * sizeof(float));
    for (int i = 0; i < qty; i++) {
        f[i] = i + 0.5f;
    }
    free(f);

    return 0;
}
