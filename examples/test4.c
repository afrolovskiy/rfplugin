#include <stdio.h>
#include <pthread.h>

int count;
pthread_mutex_t mutex;

int f1(int a) {
  return a + 1;
}


void f2(int d) {
  f1(123);
  f1(d);
  f1(count + 123);
  int a = 123;
  int ll = f1(123);
  int rr = f1(a + 123);
  int kk = f1(a + 123) + f1(123) + 123;
  int b = 3;
  int* c = &b;
  *c = f1(123);
  int** e = &c;
  int** ff = &c
  *e = *ff;
  *c = 1234;
  a = f1(*c);
}

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
