#include <stdio.h>
#include <stdlib.h>

int main() {
    float* f = (float*)malloc(150 * sizeof(float));
    if (!f) {
        perror("malloc failed");
        return 1;
    }

    for (int i = 0; i < 150; i++) {
        f[i] = i + 5.1f;
    }

    // Debugging: Print values before free
    for (int i = 0; i < 10; i++) {
        printf("f[%d] = %f\n", i, f[i]);
    }

    free(f);
    return 0;
}
