#include <pthread.h>

pthread_mutex_t fork1_mutex, fork2_mutex, fork3_mutex, fork4_mutex, fork5_mutex;
pthread_t thread1, thread2, thread3, thread4, thread5;
int fork1, fork2, fork3, fork4, fork5;

void* philosopher1(void* args) {
        while(1) {
		pthread_mutex_lock(&fork1_mutex);
	        fork1 = 1;

		pthread_mutex_lock(&fork2_mutex);
	        fork2 = 1;

		sleep(1); // eat

	        fork2 = 0;
		pthread_mutex_lock(&fork2_mutex);

	        fork1 = 0;
		pthread_mutex_lock(&fork1_mutex);
	}
	return NULL;
}

void* philosopher2(void* args) {
	while(1) {
		pthread_mutex_lock(&fork2_mutex);
        	fork2 = 1;

		pthread_mutex_lock(&fork3_mutex);
	        fork3 = 1;

		sleep(1); // eat

	        fork3 = 0;
		pthread_mutex_lock(&fork3_mutex);

	        fork2 = 0;
		pthread_mutex_lock(&fork2_mutex);
	}
	return NULL;
}

void* philosopher3(void* args) {
	while(1) {
		pthread_mutex_lock(&fork3_mutex);
	        fork3 = 1;

		pthread_mutex_lock(&fork4_mutex);
	        fork4 = 1;

		sleep(1); // eat

	        fork4 = 0;
	 	pthread_mutex_lock(&fork4_mutex);

	        fork3 = 0;
		pthread_mutex_lock(&fork3_mutex);
	}
	return NULL;
}

void* philosopher4(void* args) {
	while (1) {
		pthread_mutex_lock(&fork4_mutex);
        	fork4 = 1;

		pthread_mutex_lock(&fork5_mutex);
	        fork5 = 1;

		sleep(1); // eat

	        fork5 = 0;
		pthread_mutex_lock(&fork5_mutex);

	        fork4 = 0;
		pthread_mutex_lock(&fork4_mutex);
	}
	return NULL;
}

void* philosopher5(void* args) {
	while (1) {
		pthread_mutex_lock(&fork1_mutex);
	        fork1 = 1;

		pthread_mutex_lock(&fork5_mutex);
	        fork5 = 1;

		sleep(1); // eat

	        fork5 = 0;
		pthread_mutex_lock(&fork5_mutex);

	        fork1 = 0;
		pthread_mutex_lock(&fork1_mutex);
	}
	return NULL;
}

int main(int argc, char** argv) {
	pthread_mutex_init(&fork1_mutex, NULL);
	pthread_mutex_init(&fork2_mutex, NULL);
	pthread_mutex_init(&fork3_mutex, NULL);
	pthread_mutex_init(&fork4_mutex, NULL);
	pthread_mutex_init(&fork5_mutex, NULL);

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
