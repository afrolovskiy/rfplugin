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

        printf("reader: %d\n", buffer);

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

        buffer += 1;
        printf("writer: %d\n", buffer);

        pthread_mutex_unlock(&writer_mutex);
        pthread_mutex_unlock(&reader_mutex);
        sleep(1);
    }
    return NULL;
}

int main(int argc, char** argv) {
    pthread_t thread1, thread2, thread3, thread4, thread5, thread6;

    pthread_mutex_init(&reader_count_mutex, NULL);
    pthread_mutex_init(&reader_mutex, NULL);
    pthread_mutex_init(&writer_mutex, NULL);

    // create readers
    pthread_create(&thread1, NULL, reader, NULL);
    pthread_create(&thread1, NULL, reader, NULL);
    pthread_create(&thread1, NULL, reader, NULL);
    pthread_create(&thread1, NULL, reader, NULL);
    pthread_create(&thread1, NULL, reader, NULL);
    pthread_create(&thread1, NULL, reader, NULL);

    // create writers
    pthread_create(&thread5, NULL, writer, NULL);
    pthread_create(&thread5, NULL, writer, NULL);
    pthread_create(&thread5, NULL, writer, NULL);
    pthread_create(&thread5, NULL, writer, NULL);
    pthread_create(&thread5, NULL, writer, NULL);
    pthread_create(&thread5, NULL, writer, NULL);

    pthread_join(thread1, NULL);
    pthread_join(thread2, NULL);
    pthread_join(thread3, NULL);
    pthread_join(thread4, NULL);
    pthread_join(thread5, NULL);
    pthread_join(thread6, NULL);
    return 0;
}
