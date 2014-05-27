#include <pthread.h>

pthread_mutex_t fork1, fork2, fork3, fork4, fork5;
pthread_t thread1, thread2, thread3, thread4, thread5;

void* philosopher1(void* args) {
	pthread_mutex_lock(&fork1);
	pthread_mutex_lock(&fork2);
	sleep(1); // eat
	pthread_mutex_lock(&fork2);
	pthread_mutex_lock(&fork1);
	return NULL;
}

void* philosopher2(void* args) {
	pthread_mutex_lock(&fork2);
	pthread_mutex_lock(&fork3);
	sleep(1); // eat
	pthread_mutex_lock(&fork3);
	pthread_mutex_lock(&fork2);
	return NULL;
}

void* philosopher3(void* args) {
	pthread_mutex_lock(&fork3);
	pthread_mutex_lock(&fork4);
	sleep(1); // eat
	pthread_mutex_lock(&fork4);
	pthread_mutex_lock(&fork3);
	return NULL;
}

void* philosopher4(void* args) {
	pthread_mutex_lock(&fork4);
	pthread_mutex_lock(&fork5);
	sleep(1); // eat
	pthread_mutex_lock(&fork5);
	pthread_mutex_lock(&fork4);
	return NULL;
}

void* philosopher5(void* args) {
	pthread_mutex_lock(&fork1);
	pthread_mutex_lock(&fork5);
	sleep(1); // eat
	pthread_mutex_lock(&fork5);
	pthread_mutex_lock(&fork1);
	return NULL;
}

int main(int argc, char** argv) {
	pthread_mutex_init(&fork1, NULL);
	pthread_mutex_init(&fork2, NULL);
	pthread_mutex_init(&fork3, NULL);
	pthread_mutex_init(&fork4, NULL);
	pthread_mutex_init(&fork5, NULL);

	pthread_create(&thread1, NULL, philosopher1, NULL);
	pthread_create(&thread2, NULL, philosopher2, NULL);
	pthread_create(&thread3, NULL, philosopher3, NULL);
	pthread_create(&thread4, NULL, philosopher4, NULL);
	pthread_create(&thread5, NULL, philosopher5, NULL);

	pthread_join(thread1, NULL);
	pthread_join(thread2, NULL);
	pthread_join(thread3, NULL);
	pthread_join(thread4, NULL);
	pthread_join(thread5, NULL);

	return 0;
}
