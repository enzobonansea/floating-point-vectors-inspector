#include <stdio.h>
#include <stdlib.h>
#include <immintrin.h>

float* test_32bit_stores()
{
    int qty = 10000000;
    float* ptr_f = (float*)malloc(qty*sizeof(float));
    printf("ptr_32bit_stores=%p\n", ptr_f);
    for (int i=0; i<qty; i++) *(ptr_f+i) = 0.6f;

    return ptr_f;
}

double* test_64bit_stores()
{
    int qty = 10000000;
    double* ptr_f = (double*)malloc(qty*sizeof(double));
    printf("ptr_64bit_stores=%p\n", ptr_f);
    for (int i=0; i<qty; i++) *(ptr_f+i) = 0.6f;

    return ptr_f;
}

__m128i* test_128bit_stores()
{
    int qty = 1000000;

    // Allocate memory aligned to 16 bytes for proper SSE operation
    __m128i *ptr_128 = (__m128i *)malloc(qty * sizeof(__m128i));
    printf("ptr_128bit_stores=%p\n", ptr_128);

    // Create a 128-bit value (two 64-bit integers)
    __m128i value = _mm_set_epi64x(0xDEADBEEFDEADBEEF, 0x0123456789ABCDEF);

    // Store the 128-bit values to memory
    for (int i = 0; i < qty; i++)
    {
        _mm_store_si128(ptr_128 + i, value);
    }

    // Test different store operations that should trigger Ity_I128
    __m128i val1 = _mm_set_epi32(1, 2, 3, 4);             // Four 32-bit integers
    __m128i val2 = _mm_set_epi16(1, 2, 3, 4, 5, 6, 7, 8); // Eight 16-bit integers
    _mm_store_si128(ptr_128, val1);
    _mm_store_si128(ptr_128 + 1, val2);

    // Test some arithmetic operations that should also trigger Ity_I128
    __m128i result = _mm_add_epi32(val1, val2); // Add packed 32-bit integers
    _mm_store_si128(ptr_128 + 2, result);

    return ptr_128;
}

int main() {
    float*      ptr1    = test_32bit_stores();
    double*     ptr2    = test_64bit_stores();
    __m128i*    ptr3    = test_128bit_stores();

    free(ptr1);
    free(ptr2);
    free(ptr3);

    return 0;
}