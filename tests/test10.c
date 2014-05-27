#include <pthread.h>

pthread_t thread1, thread2;
pthread_mutex_t mutex;
int x = 0;

void* run(void* args) {
	while (1) {
		pthread_mutex_lock(&mutex);
		if (x > 1000)
			break;
		x++;
		pthread_mutex_unlock(&mutex);
		
	}
	return NULL;
}

int main(int argc, char** argv) {
	pthread_mutex_init(&mutex, NULL);
	pthread_create(&thread1, NULL, run, NULL);
        pthread_create(&thread2, NULL, run, NULL);
	pthread_mutex_destroy(&mutex);        
	return 0;
}

