#include "selectivity_budget.h"
#include <cassert>
#include <cstdio>
#include <iostream>

int main() {
  using course_lab::choose_budget;
  assert(choose_budget(1.0,320,8192)==320);
  assert(choose_budget(.1,320,8192)==320);
  assert(choose_budget(.00545,320,8192)==5888);
  assert(choose_budget(.002499,320,8192)==8192);
  assert(choose_budget(0,320,8192)==8192);
  for (double s : {0.0, .0001, .005, .05, .5, 1.0}) {
    auto l = choose_budget(s,320,8192);
    assert(l>=320 && l<=8192);
  }
  bool rejected=false;
  try { choose_budget(-.1,320,8192); } catch (const std::invalid_argument &) {rejected=true;}
  assert(rejected);
  // Duplicate labels and explicit zero-valued CSR entries must not inflate
  // document frequencies; counts are per vector, rather than per CSR entry.
  const char *file = "/tmp/fvs-budget-test.spmat";
  int64_t h[]={3,4,6}, ptr[]={0,3,5,6};
  int32_t idx[]={1,1,2,1,2,3};
  float values[]={1,1,0,1,1,1};
  {
    std::ofstream out(file,std::ios::binary);
    out.write((char*)h,sizeof(h));out.write((char*)ptr,sizeof(ptr));
    out.write((char*)idx,sizeof(idx));out.write((char*)values,sizeof(values));
  }
  course_lab::LabelFrequency f; f.load(file);
  assert(f.nodes()==3 && f.count(1)==2 && f.count(2)==1 && f.count(0)==0);
  uint32_t q[]={1,1}, empty[]={0}, unknown[]={1,9}, multi[]={2,1,2};
  assert(std::abs(f.selectivity(q)-2.0/3)<1e-9);
  assert(f.selectivity(empty)==1 && f.selectivity(unknown)==0);
  rejected=false;
  try { f.selectivity(multi); } catch(const std::invalid_argument &) {rejected=true;}
  assert(rejected);
  std::remove(file);
  std::cout << "BUDGET_AND_CSR_TEST_PASS\n";
}
