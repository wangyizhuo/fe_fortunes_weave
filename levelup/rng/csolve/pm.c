#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
static inline uint32_t spread(uint32_t p, uint32_t i){ return 0x6C078965u*(p^(p>>30))+i; }
static int cmp(const void*a,const void*b){uint32_t x=*(uint32_t*)a,y=*(uint32_t*)b;return x<y?-1:x>y;}
int main(int argc,char**argv){
  int n=argc-1; uint32_t*t=malloc(4*n); for(int i=0;i<n;i++)t[i]=strtoul(argv[i+1],0,10);
  qsort(t,n,4,cmp);
  #pragma omp parallel for schedule(static)
  for(int64_t s0=0;s0<(1LL<<31);s0++){
    uint32_t x=spread((uint32_t)s0,0), y=spread(x,1), z=spread(y,2), w=spread(z,3);
    uint32_t tt=x^(x<<11); uint32_t r=(tt^(tt>>8)^w^(w>>19))&0x7FFFFFFFu;
    if(bsearch(&r,t,n,4,cmp)){
      #pragma omp critical
      printf("%u %u\n",(uint32_t)s0,r);
    }
  }
}
