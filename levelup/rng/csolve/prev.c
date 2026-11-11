// 找所有 s 使 next_seed(s) == target（种子往回推一步，可能多个）。
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
static inline uint32_t spread(uint32_t p, uint32_t i){ return 0x6C078965u*(p^(p>>30))+i; }
int main(int argc,char**argv){
  uint32_t t=(uint32_t)strtoul(argv[1],0,10);
  #pragma omp parallel for schedule(static)
  for(int64_t s0=0;s0<(1LL<<31);s0++){
    uint32_t x=spread((uint32_t)s0,0), y=spread(x,1), z=spread(y,2), w=spread(z,3);
    uint32_t tt=x^(x<<11); uint32_t r=(tt^(tt>>8)^w^(w>>19))&0x7FFFFFFFu;
    if(r==t){
      #pragma omp critical
      printf("%u\n",(uint32_t)s0);
    }
  }
}
