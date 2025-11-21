/*******************************************************************************
 *
 *  Project:        quTAG User Library
 *
 *  Filename:       example8.c
 *
 *  Purpose:        Simple example for use of tdcbase lib
 *                  Feature Heralded G(2) Functions
 *
 *  Author:         NHands GmbH & Co KG
 *
 *******************************************************************************/
/* $Id: example8.c,v 1.1 2020/09/03 13:57:02 trurl Exp $ */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "tdcbase.h"
#include "tdchg2.h"

#ifdef unix
#include <unistd.h>
#define SLEEP(x) usleep(x*1000)
#else
#include <windows.h>
#define SLEEP(x) Sleep(x)
#endif

#define BINWIDTH   30000
#define BINCOUNT      41   /* suitable for 100 kHz Signal */
#define CHI            1   /* Channel numbers to use */
#define CH1            2
#define CH2            4

static void checkRc( const char * fctname, int rc )
{
  if ( rc ) {
    printf( ">>> %s: %s\n", fctname, TDC_perror( rc ) );
    TDC_deInit();
    exit( 1 );
  }
}


static void collectEvents( int msecs )
{
  Int64 evtIdler, evtCoinc;
  int   sleeptime = 0, step = 250, rc;

  while ( sleeptime < msecs ) {
    SLEEP( step );
    sleeptime += step;
    rc = TDC_getHg2Raw( &evtIdler, &evtCoinc, NULL, NULL, NULL );
    printf( "%5dms: %6"LLDFORMAT" idler evts, %6"LLDFORMAT" coinc evts\n",
            sleeptime, evtIdler, evtCoinc );
  }
}
  

#define MYMAX(a,b) ((a)>(b) ? (a) : (b))

static void printMap( Int64 * bufTcp, int binCount )
{
  int i, j;
  char map[] = "  --~~++ooOO00XX%%";
  Int64 maxTcp = 0;
  for( i = 0; i < binCount * binCount; i++ ) {
    maxTcp = MYMAX( maxTcp, bufTcp[i] );
  }
  printf( "\ncb: \"%s\"\n", map );
  printf( "-" );
  for( j = 0; j < binCount; j++ ) {
    printf( j == binCount/2 ? "\\/" : "--" );
  }
  printf( "-\n" );
  for( i = 0; i < binCount; i++ ) {
    printf( i == binCount/2 ? ">" : "|" );
    for( j = 0; j < binCount; j++ ) {
      int index = 2 * (int) ( bufTcp[i*binCount+j] / maxTcp * 8 );
      printf( "%.2s", map + index );
    }
    printf( i == binCount/2 ? "<\n" : "|\n" );
  }
  printf( "-" );
  for ( j = 0; j < binCount; j++ ) {
    printf( j == binCount/2 ? "/\\" : "--" );
  }
  printf( "-\n" );
}


static int run( double threshold )
{
  int i, rc, filledBins = 0;
  double timeBase;
  double bufg2[BINCOUNT];
  Int64  buftcp[BINCOUNT*BINCOUNT];
  Int32  bufsize = BINCOUNT;

  rc = TDC_init( -1 );
  checkRc( "TDC_init", rc );
  rc = TDC_getTimebase( &timeBase );
  rc = TDC_enableChannels( 1, 0xff );
  checkRc( "TDC_enableChannels", rc );
  rc = TDC_enableHg2( 1 );
  checkRc( "TDC_enableHg2", rc );
  rc = TDC_setHg2Params( BINWIDTH, BINCOUNT );
  checkRc( "TDC_setHg2Params", rc );
  rc = TDC_setHg2Input( CHI, CH1, CH2 );
  checkRc( "TDC_setHg2Input", rc );
  rc = TDC_configureSignalConditioning( CHI, SCOND_MISC, 1, threshold );
  checkRc( "TDC_configureSignalConditioning(1,...)", rc );
  rc = TDC_configureSignalConditioning( CH1, SCOND_MISC, 1, threshold );
  checkRc( "TDC_configureSignalConditioning(1,...)", rc );
  rc = TDC_configureSignalConditioning( CH2, SCOND_MISC, 1, threshold );
  checkRc( "TDC_configureSignalConditioning(2,...)", rc );

  collectEvents( 3000 );

  rc = TDC_calcHg2G2(  bufg2,  &bufsize, 0 );
  checkRc( "TDC_calcHg2G2", rc );
  for ( i = 0; i < bufsize; ++i ) {
    printf( "%4d: g2(%6gns) = %8g\n",
            i, .001 * BINWIDTH * (i-BINCOUNT/2), bufg2[i] );
  }
  bufsize = BINCOUNT * BINCOUNT;
  rc = TDC_calcHg2Tcp1D( buftcp, &bufsize, 0 );
  for ( i = 0; i < bufsize; ++i ) {
    if ( buftcp[i] != 0 ) {
      printf( "Tcp[%3d][%3d] = %8"LLDFORMAT"\n", i / BINCOUNT, i % BINCOUNT, buftcp[i] );
    }
  }
  printMap( buftcp, BINCOUNT );
  checkRc( "TDC_calcHg2Tcp", rc );
  TDC_deInit();
  return 0;
}



int main( int argc, char ** argv )
{
  double threshold = 1.0;

  printf( "\nquTAG example \"Heralded G(2) Functions\".\n\n" );
  if ( argc <= 1 ) {
    printf( "Connect a generated signal to channels %d (idler), %d and %d\n"
            "and call the program with a threshold value\n"
            "below the signal level.\n"
            "Usage %s <threshold[V]>.\n\n", CHI, CH1, CH2, argv[0] );
    return 1;
  }

  sscanf( argv[1], "%lg", &threshold );
  return run( threshold );
}
