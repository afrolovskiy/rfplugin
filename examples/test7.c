#include <stdio.h>
#include <pthread.h>

int count;
int* pcount;
int** ppcount;
pthread_mutex_t mutex;
pthread_mutex_t* pmutex;
pthread_mutex_t** ppmutex;

void bar(int *pcount) {
  int lcount, *pcount2;
  pcount2 = pcount;

  pthread_mutex_lock(&mutex);

  lcount = *pcount2;
  lcount = lcount + 1;
  *pcount2 = lcount;

  pthread_mutex_unlock(&mutex);
}

void *foo(void *args) {
  int i, *pcount;

  pcount = (int *) args;
  *pcount = 132;

  for (i = 0; i < 1000; i++) {
    bar(pcount);
  }

  return NULL;
}

int main(int argc, char *argv[]) {
  int i, rc;
  pthread_t threads[2];

  count = 0;

  pthread_mutex_init(&mutex, NULL);

  rc = pthread_create(&threads[0], NULL, foo, &count);
  rc = pthread_create(&threads[1], NULL, foo, &count);


  pthread_mutex_destroy(&mutex);

  return 0;
}
