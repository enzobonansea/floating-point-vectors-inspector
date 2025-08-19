#include <stdio.h>
#include <stdlib.h>
#include <immintrin.h>

float* test_32bit_stores()
{
    int qty = 10000;
    float* ptr_f = (float*)malloc(qty*sizeof(float));
    printf("ptr_32bit_stores=%p\n", ptr_f);
    for (int i=0; i<qty; i++) *(ptr_f+i) = 0.6f;

    return ptr_f;
}

double* test_64bit_stores()
{
    int qty = 10000;
    double* ptr_f = (double*)malloc(qty*sizeof(double));
    printf("ptr_64bit_stores=%p\n", ptr_f);
    for (int i=0; i<qty; i++) *(ptr_f+i) = 0.6f;

    return ptr_f;
}

__m128i* test_128bit_stores()
{
    int qty = 1000;

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

__m256i* test_256bit_stores()
{
    int qty = 1000;

    // Allocate memory aligned to 32 bytes for proper AVX operation
    __m256i *ptr_256 = (__m256i *)malloc(qty * sizeof(__m256i));
    printf("ptr_256bit_stores=%p\n", ptr_256);

    // Create a 256-bit value
    __m256i value = _mm256_set_epi64x(0xDEADBEEFDEADBEEF, 0x0123456789ABCDEF, 
                                      0xFEDCBA9876543210, 0xAABBCCDDEEFF0011);

    // Store the 256-bit values to memory
    for (int i = 0; i < qty; i++)
    {
        _mm256_store_si256(ptr_256 + i, value);
    }

    // Test different store operations that should trigger 256-bit operations
    __m256i val1 = _mm256_set_epi32(1, 2, 3, 4, 5, 6, 7, 8);          // Eight 32-bit integers
    __m256i val2 = _mm256_set_epi16(1, 2, 3, 4, 5, 6, 7, 8, 
                                     9, 10, 11, 12, 13, 14, 15, 16);   // Sixteen 16-bit integers
    _mm256_store_si256(ptr_256, val1);
    _mm256_store_si256(ptr_256 + 1, val2);

    // Test some arithmetic operations with 256-bit values
    __m256i result = _mm256_add_epi32(val1, val2); // Add packed 32-bit integers
    _mm256_store_si256(ptr_256 + 2, result);

    return ptr_256;
}

int main() {
    float*      ptr1    = test_32bit_stores();
    free(ptr1);

    double*     ptr2    = test_64bit_stores();
    free(ptr2);
    
    __m128i*    ptr3    = test_128bit_stores();
    free(ptr3);

    __m256i*    ptr4    = test_256bit_stores();
    free(ptr4);

    return 0;
}