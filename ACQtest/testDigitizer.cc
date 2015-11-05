#include "ACQ/Device.hh"
#include <iostream>

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
  for (size_t i=0; i<dev.NumSites(); i++ ) {
    cout << "  Site: " << i << ", Num channels: " << dev.NumChannels(i) << endl;
  }
  cout << "size of ADC word (bytes): " << dev.ReadoutSize() << endl;
  
  cout << "Help output: " << endl << dev.SendCommand("help") << endl;

  return 0;
}
