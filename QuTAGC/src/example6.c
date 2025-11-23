/*******************************************************************************
 *
 *  Project:        TDC User Library
 *
 *  Filename:       example6.c
 *
 *  Purpose:        Small performance test
 *
 *  Author:         NHands GmbH & Co KG
 *
 *******************************************************************************/
/* $Id: example6.c,v 1.4 2021/01/12 14:44:50 trurl Exp $ */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include "tdcbase.h"

#ifdef unix
#include <unistd.h>
#include <sys/time.h>
#define SLEEP(x) usleep(x*1000)
#else
#include <windows.h>
#define SLEEP(x) Sleep(x)
#endif


#define BUFSIZE 1000000

static void checkRc( const char * fctname, int rc )
{
  if ( rc ) {
    printf( ">>> %s: %s\n", fctname, TDC_perror( rc ) );
    TDC_deInit();
    exit( 1 );
  }
}


double timestamp()
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
 * Performance test using the device internal selftest
 */
int main( int argc, char ** argv )
{
  double startTime, actTime;
  Int32  delays[] = { 0, 10, 20, 30, 20, 10, 0, -10 };
  const  char * fileNames[]   = { "", "timestamps.bin", "timestamps.bin", "timestamps.txt" };
  const  Int32  fileFormats[] = { FORMAT_NONE, FORMAT_BINARY, FORMAT_COMPRESSED, FORMAT_ASCII };
  Int32  rc, i, lost = 0, hadLost = 0, received = 0, valid = 0;
  Int32  runTime = argc >= 2 ? atoi( argv[1] ) :  10;
  Int32  chCount = argc >= 3 ? atoi( argv[2] ) :   1;
  Int32  bSize   = argc >= 4 ? atoi( argv[3] ) :  20;
  Int32  bDist   = argc >= 5 ? atoi( argv[4] ) : 125;
  Int32  toDisk  = argc >= 6 ? atoi( argv[5] ) :   0;
  Int32  delComp = argc >= 7 ? atoi( argv[6] ) :   0;
  Int32  bPeriod = 4;
  double rate    = chCount * bSize / (bDist * 1.6e-8);
  printf( "\nUsage: %s <runTime> <chCount> <burstSize> <burstDist> <toDisk> <delayComp>"
          "\n       runTime:   runtime of program [s]            -> %d"
          "\n       chCount:   number of channels firing         -> %d"
          "\n       burstSize: number of signals in a burst      -> %d"
          "\n       burstDist: distance between bursts [16ns]    -> %d"
          "\n       toDisk:    write timestamps to disk (0/1/2/3)-> %d"
          "\n       delayComp: switch on delay compens. (0/1)    -> %d"
          "\nResulting data rate: %g kSamples/s\n",
          argv[0], runTime, chCount, bSize, bDist, toDisk, delComp, rate / 1000. );

  rc = TDC_init( -1 );
  checkRc( "TDC_init", rc );
  rc = TDC_setTimestampBufferSize( BUFSIZE );
  checkRc( "TDC_setTimestampBufferSize", rc );
  rc = TDC_enableChannels( 1, 0xffffffff );
  checkRc( "TDC_enableChannels", rc );
  for ( i = 0; i < 8; ++i ) {
    rc = TDC_setChannelDelay( i + 1, delComp ? delays[i] : 0 );
    checkRc( "TDC_setChannelDelay", rc );
  }
  rc = TDC_configureSelftest( (2<<chCount) - 1, bPeriod /*5ns*/, bSize, bDist /*20ns*/ );
  checkRc( "TDC_configureSelftest", rc );
  //  TDC_freezeBuffers( 1 );
  //  checkRc( "TDC_freezeBuffers", rc );

  TDC_writeTimestamps( fileNames[toDisk], fileFormats[toDisk] );
  checkRc( "TDC_writeTimestamps", rc );

  startTime = timestamp();
  while ( timestamp() - startTime < runTime ) {
    TDC_getDataLost( &lost );
    if ( lost != hadLost ) {
      printf( lost ? "Data loss %6.2fs ... " : "%6.2fs\n", timestamp() - startTime );
      fflush( stdout );
      hadLost = lost;
    }
    TDC_getLastTimestamps( 1, NULL, NULL, &valid );
    if ( valid >= BUFSIZE ) {
      printf( "Timestamp buffer too small\n" );
    }
    received += valid;
    SLEEP( 10 );
  }
  if ( hadLost ) {
    printf( "%6.2fs\n", timestamp() - startTime );
  }

  actTime = timestamp() - startTime;
  TDC_writeTimestamps( 0, 0 );

  printf( "Received %d timestamps, %f kSamples/s\n", received, .001 * received / actTime );
  if ( toDisk ) {
    double expected = rate * actTime * 1.e-5 * (toDisk == 1 ? 1. : 0.5);
    printf( "Runtime: %g s; expected file size: %g MB\n", actTime, expected );
  } 
  TDC_deInit();
  return 0;
}
