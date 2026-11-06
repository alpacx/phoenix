typedef int SemaphoreHandle_t;
static inline int xSemaphoreCreateMutex(void){return 1;}
static inline void xSemaphoreTake(int a,int b){(void)a;(void)b;}
static inline void xSemaphoreGive(int a){(void)a;}
