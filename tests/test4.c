#include <stdio.h>
#include <pthread.h>

int buffer = 0;
int reader_count = 0;
pthread_mutex_t reader_count_mutex;
pthread_mutex_t reader_mutex;
pthread_mutex_t writer_mutex;

void* reader(void* args) {
    while (1) {
        pthread_mutex_lock(&reader_count_mutex);
        if (reader_count == 0) {
            pthread_mutex_lock(&reader_mutex);
        }
        reader_count += 1;
        pthread_mutex_unlock(&reader_count_mutex);

        int* pbuffer = (int *) args;
        printf("reader: %d\n", *pbuffer);

        pthread_mutex_lock(&reader_count_mutex);
        reader_count -= 1;
        if (reader_count == 0) {
            pthread_mutex_unlock(&reader_mutex);
        }
        pthread_mutex_unlock(&reader_count_mutex);
        sleep(1);
    }
    return NULL;
}

void* writer(void* args) {
    while (1) {
        pthread_mutex_lock(&reader_mutex);
        pthread_mutex_lock(&writer_mutex);

        int* pbuffer  = (int *) args;
        (*pbuffer)++;
        printf("writer: %d\n", *pbuffer);

        pthread_mutex_unlock(&writer_mutex);
        pthread_mutex_unlock(&reader_mutex);
        sleep(1);
    }
    return NULL;
}

int main(int argc, char** argv) {
    pthread_t thread1, thread2, thread3, thread4;

    pthread_mutex_init(&reader_count_mutex, NULL);
    pthread_mutex_init(&reader_mutex, NULL);
    pthread_mutex_init(&writer_mutex, NULL);

    // create readers
    pthread_create(&thread1, NULL, reader, &buffer);
    pthread_create(&thread2, NULL, reader, &buffer);

    // create writers
    pthread_create(&thread3, NULL, writer, &buffer);
    pthread_create(&thread4, NULL, writer, &buffer);

    pthread_join(thread1, NULL);
    pthread_join(thread2, NULL);
    pthread_join(thread3, NULL);
    pthread_join(thread4, NULL);
    return 0;
}
