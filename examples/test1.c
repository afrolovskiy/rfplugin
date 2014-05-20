#include <stdio.h>
/*struct struct1 {
  int a;
  int* b;
};

typedef struct struct2 {
  int a;
  int* b;
} struct3;
*/

int x;
//struct struct1 z;
//struct3 w;

int main(int argc, char** argv)
{
  // pointers to simple types
  int u = 1;
  u = x + x + 1;
  int *y = &x;
  int *c;
  c = y;
  int** l = &y;
  int* k;
  k = *l;
  if (u > 0)
    *l = &u;
  else
    u =x;

  // work with structures
  //struct3 t;
  //int* aa = &t.a;
  return 0;
}

