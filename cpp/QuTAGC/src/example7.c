/*******************************************************************************
 *
 *  Project:        TDC User Library
 *
 *  Filename:       example7.c
 *
 *  Purpose:        Mutli device handling example
 *
 *  Author:         NHands GmbH & Co KG
 *
 *******************************************************************************/
/* $Id: example7.c,v 1.1 2020/09/03 13:57:02 trurl Exp $ */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include "tdcbase.h"
#include "tdcmultidev.h"

#ifdef unix
#include <unistd.h>
#include <sys/time.h>
#define SLEEP(x) usleep(x*1000)
#else
#include <windows.h>
#define SLEEP(x) Sleep(x)
#endif


#define BUFSIZE 200000

static void checkRc( const char * fctname, unsigned int devNo, int rc )
{
  if ( rc ) {
    printf( ">>> %s - Dev %d: %s\n", fctname, devNo, TDC_perror( rc ) );
    TDC_deInit();
    exit( 1 );
  }
}


static double timestamp()
{
#ifdef unix
  struct timeval tv;
  gettimeofday( &tv, 0 );
  return tv .tv_sec + tv .tv_usec / 1.e6;
#else
  return GetTickCount() / 1000.;
#endif
}


/*
 * List all devices and connect to all of them
 */
static unsigned int connectAllDevices()
{
  unsigned int devNo = 0, devCount = 0;
  int rc = TDC_discover( &devCount );
  checkRc( "TDC_discover", -1, rc );
  printf( "Found %d devices:\n", devCount );
  for ( devNo = 0; devNo < devCount; ++devNo ) {
    char serNo[16];
    TDC_DevType type;
    int devId;
    rc = TDC_getDeviceInfo( devNo, &type, &devId, serNo, NULL );
    checkRc( "TDC_getDeviceInfo", devNo, rc );
    printf( "   Dev %d: Id=%d, SerialNo=%s\n", devNo, devId, serNo );
    rc = TDC_connect( devNo );
    checkRc( "TDC_connect", devNo, rc );
  }
  return devCount;
}


/* All data associated with a device */
struct Device {
  Int32 received;  /* Timestamps received */
};

/*
 * Performance test using the device internal selftest
 */
int main( int argc, char ** argv )
{
  struct Device devs[10];
  unsigned int devCount, devNo;
  double startTime, actTime;
  Int32  rc, valid;
  Int32  runTime = argc >= 2 ? atoi( argv[1] ) :  10;
  printf( "\nMulti Device Demo.\nUsage: %s <runTime[s]>\n\n", argv[0] );

  memset( devs, 0, sizeof( devs ) );
  devCount = connectAllDevices();
  if ( devCount == 0 || devCount > 10 ) {
    return -1;
  }

  /* configure devices with different data rates */
  for ( devNo = 0; devNo < devCount; devNo++ ) {
    Int32 burstDist = (Int32) (125 * (devNo / 3. + 1.));
    rc = TDC_addressDevice( devNo );
    checkRc( "TDC_addressDevice", devNo, rc );
    rc = TDC_setTimestampBufferSize( BUFSIZE );
    checkRc( "TDC_setTimestampBufferSize", devNo, rc );
    rc = TDC_enableChannels( 1, 0xff );
    checkRc( "TDC_enableChannels", devNo, rc );
    rc = TDC_configureSelftest( 1, 5, 20, burstDist );
    checkRc( "TDC_configureSelftest", devNo, rc );
  }

  /* collect data from all devs */
  startTime = timestamp();
  while ( timestamp() - startTime < runTime ) {
    for ( devNo = 0; devNo < devCount; devNo++ ) {
      TDC_addressDevice( devNo );
      TDC_getLastTimestamps( 1, NULL, NULL, &valid );
      if ( valid >= BUFSIZE ) {
        printf( "Timestamp buffer too small, dev %d\n", devNo );
      }
      devs[devNo] .received += valid;
    }
    SLEEP( 10 );
  }
  actTime = timestamp() - startTime;

  printf( "\nNumber of Timestamps received:\n" );
  for ( devNo = 0; devNo < devCount; devNo++ ) {
    printf( "   Dev %d: %d samples, %f kSamples/s\n",
            devNo, devs[devNo] .received,  .001 * devs[devNo] .received / actTime );
  }

  TDC_deInit();
  return 0;
}
