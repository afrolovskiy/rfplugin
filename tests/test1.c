#include <pthread.h>
#include <stdio.h>

pthread_mutex_t m1, m2;
int x, y;


void munge(int* value, pthread_mutex_t* mutex) {
    pthread_mutex_lock(mutex);
    (*value) += 1;
    pthread_mutex_unlock(mutex);
}

void* run_thread1(void* args) {
    //int* pcount = (int *) args;
    //*pcount = 125;
    munge(&x, &m1);
    munge(&y, &m2);
    return NULL;
}

void* run_thread2(void* args) {
    //int* pcount = (int *) args;
    //*pcount = 123;
    munge(&x, &m1);
    munge(&y, &m1);
    return NULL;
}



int main(int argc, char** argv) {
    pthread_t thread1, thread2;

    int count = 0;

    pthread_mutex_init(&m1, NULL);
    pthread_mutex_init(&m2, NULL);

    pthread_create(&thread1, NULL, run_thread1, &count);
    pthread_create(&thread2, NULL, run_thread2, &count);

    pthread_join(thread1, NULL);
    pthread_join(thread2, NULL);

    pthread_mutex_destroy(&m1);
    pthread_mutex_destroy(&m2);

    return 0;
}

