#include <pthread.h>

pthread_mutex_t m1, m2, m3;
int x, y, z;


void munge(int* value, pthread_mutex_t* mutex) {
    pthread_mutex_lock(mutex);
    (*value) += 1;
    pthread_mutex_unlock(mutex);
}

void* run_thread1(void* args) {
    munge(&x, &m1);
    munge(&y, &m2);
    return NULL;
}

void* run_thread2(void* args) {
    munge(&x, &m1);
    munge(&y, &m1);
    return NULL;
}

void* run_thread3(void* args) {
    munge(&x, &m1);
    munge(&z, &m3);
    return NULL;
}

int main(int argc, char** argv) {
    pthread_t thread1, thread2;

    x = 0;
    y = 0;
    z = 0;

    pthread_mutex_init(&m1, NULL);
    pthread_mutex_init(&m2, NULL);
    pthread_mutex_init(&m3, NULL);

    pthread_create(&thread1, NULL, run_thread1, NULL);
    pthread_create(&thread2, NULL, run_thread2, NULL);
    pthread_create(&thread2, NULL, run_thread3, NULL);

    return 0;
}

