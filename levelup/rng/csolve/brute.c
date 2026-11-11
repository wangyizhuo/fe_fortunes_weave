// 全种子暴力搜索：stdin 每行一步 "g0..g8 mask"，g 为显示顺序成长率，mask 为 9 位加点（显示顺序 bit i），-1 = 这一步不核对。
// 第 11 列 same=1：和上一行用同一个种子（同一级换职业的两次预览）。
// argv[1] = 允许对不上的总项数。输出所有满足的「第一步种子」。
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
static const int ORD[9] = {0,1,2,4,3,7,5,6,8};
static int G[64][9], M[64], SAME[64], N;
static inline uint32_t spread(uint32_t p, uint32_t i){ return 0x6C078965u*(p^(p>>30))+i; }
typedef struct { uint32_t x,y,z,w; } X;
static inline void xinit(X*r,uint32_t s){ r->x=spread(s,0); r->y=spread(r->x,1); r->z=spread(r->y,2); r->w=spread(r->z,3); }
static inline uint32_t xnext(X*r){ uint32_t t=r->x^(r->x<<11); uint32_t res=t^(t>>8)^r->w^(r->w>>19); r->x=r->y; r->y=r->z; r->z=r->w; r->w=res; return res; }
static inline uint32_t nseed(uint32_t s){ X r; xinit(&r,s); return xnext(&r)&0x7FFFFFFFu; }
static int levelup(uint32_t seed, const int *gd){
  int g[9], cand[9], nc=0, gains[9];
  for(int k=0;k<9;k++){ g[k]=gd[ORD[k]]<0?0:gd[ORD[k]]; if(g[k]>=1) cand[nc++]=k; }
  X r; xinit(&r,seed);
  int floor_=nc<2?nc:2, target=floor_>1?floor_:1;
  for(int a=0;a<4;a++){
    int grown=0;
    for(int k=0;k<9;k++) gains[k]=0;
    for(int c=0;c<nc;c++){ int k=cand[c]; int sure=g[k]/100, rem=g[k]%100; gains[k]=sure;
      if(rem>0){ uint32_t roll=(xnext(&r)&0x7FFFFFFFu)%1000000u; if(roll<(uint32_t)rem*10000u) gains[k]++; } }
    for(int c=0;c<nc;c++) if(gains[cand[c]]) grown++;
    if(grown>=target||a==3) break;
  }
  int have=0; for(int c=0;c<nc;c++) if(gains[cand[c]]) have++;
  int missing=floor_-have;
  while(missing>0){ int tw=0; for(int c=0;c<nc;c++) if(!gains[cand[c]]) tw+=100*g[cand[c]]; if(tw<=0) break;
    int pick=(xnext(&r)&0x7FFFFFFFu)%tw;
    for(int c=0;c<nc;c++){ int k=cand[c]; if(gains[k]) continue; pick-=100*g[k]; if(pick<0){ gains[k]=1; break; } }
    missing--; }
  int mask=0; for(int k=0;k<9;k++) if(gains[k]) mask|=1<<ORD[k]; return mask;
}
int main(int argc,char**argv){
  int tol=argc>1?atoi(argv[1]):0;
  while(N<64 && scanf("%d %d %d %d %d %d %d %d %d %d %d",&G[N][0],&G[N][1],&G[N][2],&G[N][3],&G[N][4],&G[N][5],&G[N][6],&G[N][7],&G[N][8],&M[N],&SAME[N])==11) N++;
  #pragma omp parallel for schedule(dynamic,65536)
  for(int64_t s0=0;s0<(1LL<<31);s0++){
    uint32_t s=(uint32_t)s0; int miss=0, ok=1;
    for(int i=0;i<N;i++){
      if(M[i]>=0){ int m=levelup(s,G[i])^M[i]; miss+=__builtin_popcount(m); if(miss>tol){ok=0;break;} }
      if(i+1<N && !SAME[i+1]) s=nseed(s);
    }
    if(ok){
      #pragma omp critical
      { printf("%u %d\n",(uint32_t)s0,miss); fflush(stdout); }
    }
  }
  return 0;
}
