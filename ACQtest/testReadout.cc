#include "ACQ/Device.hh"
#include <iostream>
#include <chrono>
#include <thread>

using namespace std;

int main(int argc, char** argv) 
{
  if (argc != 2) {
    cout << "Usage: prog ip_addr_of_digitizer" << endl;
    return 1;
  }
  acq::Device dev(argv[1]);
  cout << "IP Address: " << dev.IPAddress() << endl;
  cout << "Num sites: " << dev.NumSites() << endl;

  typedef int16_t readoutType;  // 16-bit cards
  //typedef int32_t readoutType; // 32-bit cards
  dev.BeginReadout<readoutType>( [] (acq::Device::DevTempl<readoutType>::ptr_type ptr) {
    // This function runs in a separate thread
    cout << (*ptr)[0] << endl;
  },
  1024*1024 // Buffer size (in bytes)
  );
   
  // Wait for 2 s then call stop
  std::this_thread::sleep_for(std::chrono::seconds(2)); 
  dev.StopReadout();

  return 0;
}
