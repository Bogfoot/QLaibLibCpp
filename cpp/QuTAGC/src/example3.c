/*******************************************************************************
 *
 *  Project:        TDC User Library
 *
 *  Filename:       example3.c
 *
 *  Purpose:        Simple example for use of tdcbase lib
 *                  Timestamp delay compensation
 *
 *  Author:         NHands GmbH & Co KG
 *
 *******************************************************************************/
/* $Id: example3.c,v 1.3 2021/03/11 19:45:06 trurl Exp $ */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "tdcbase.h"
#include "tdcstartstop.h"

#ifdef unix
#include <unistd.h>
#define SLEEP(x) usleep(x*1000)
#else
#include <windows.h>
#define SLEEP(x) Sleep(x)
#endif


#define BINCOUNT      25  /* Histogram size */
#define BINWIDTH     100  /* Histogram bin width */
#define CH1            1  /* first channel to use */
#define CH2            7  /* 2nd channel to use */
#define CHMASK  ((1<<(CH1-1))|(1<<(CH2-1)))  /* Channel mask */



static void checkRc( const char * fctname, int rc )
{
  if ( rc ) {
    printf( ">>> %s: %s\n", fctname, TDC_perror( rc ) );
    TDC_deInit();
    exit( 1 );
  }
}


void collectEvents( int msecs, const char * header )
{
  int j;
  Int32 tooBig1, tooBig2, hist1[BINCOUNT], hist2[BINCOUNT];
  double tdc2ns;
  TDC_getTimebase( &tdc2ns );
  tdc2ns *= 1.e9;
  printf( "\nTime Diff Histograms %d/%d: %s\n", CH1, CH2, header );
  printf( " Time diff [ns]  Count %d-after-%d  Count %d-after-%d\n", CH1, CH2, CH2, CH1 );

  SLEEP( 10 );
  TDC_getHistogram( CH1, CH2, 1, hist1, 0, 0, &tooBig1, 0, 0, 0 ); /* clear old stuff */
  TDC_getHistogram( CH2, CH1, 1, hist2, 0, 0, &tooBig2, 0, 0, 0 );

  SLEEP( msecs );
  TDC_freezeBuffers( 1 );
  TDC_getHistogram( CH1, CH2, 1, hist1, 0, 0, &tooBig1, 0, 0, 0 );
  TDC_getHistogram( CH2, CH1, 1, hist2, 0, 0, &tooBig2, 0, 0, 0 );
  TDC_freezeBuffers( 0 );
  for ( j = 0; j < BINCOUNT; ++j ) {
    printf( "%16f %16d %16d\n", j*BINWIDTH*tdc2ns, hist1[j], hist2[j] );
  }
  printf( "       ...       %16d %16d\n", tooBig1, tooBig2 );
  printf( "\n" );
}
  


int run( double threshold, Int32 delay2, Int32 delay1 )
{
  int rc;

  rc = TDC_init( -1 );
  checkRc( "TDC_init", rc );
  rc = TDC_enableChannels( 0, CHMASK );
  checkRc( "TDC_enableChannels", rc );
  rc = TDC_configureSignalConditioning( CH1, SCOND_MISC, 1, threshold );
  checkRc( "TDC_configureSignalConditioning(1,...)", rc );
  rc = TDC_configureSignalConditioning( CH2, SCOND_MISC, 1, threshold );
  checkRc( "TDC_configureSignalConditioning(2,...)", rc );
  rc = TDC_enableStartStop( 1 );                       /* Use start stop histograms */
  checkRc( "TDC_enableStartStop", rc );
  rc = TDC_setHistogramParams( BINWIDTH, BINCOUNT );
  checkRc( "TDC_setHistogramParams", rc );
  rc = TDC_addHistogram( CH1, CH2, 1 );
  checkRc( "TDC_addHistogram 1-2", rc );
  rc = TDC_addHistogram( CH2, CH1, 1 );
  checkRc( "TDC_addHistogram 2-1", rc );

  rc = TDC_setChannelDelay( CH1, 0 );
  checkRc( "TDC_setChannelDelay 1", rc );
  rc = TDC_setChannelDelay( CH2, 0 );
  checkRc( "TDC_setChannelDelay 2", rc );
  collectEvents( 1000, "Without compensation" );

  rc = TDC_setChannelDelay( CH1, delay1 );
  checkRc( "TDC_setChannelDelay 3", rc );
  rc = TDC_setChannelDelay( CH2, delay2 );
  checkRc( "TDC_setChannelDelay 4", rc );
  collectEvents( 1000, "Now with compensation" );

  TDC_deInit();
  return 0;
}


int main( int argc, char ** argv )
{
  double threshold = 1.;
  Int32  delay1 = 0, delay2 = 0;
  if ( argc <= 2 ) {
    printf( "\nTDC timestamp delay example.\n\n"
            "Connect a generated signal to channels %d and %d\n"
            "with cables of different length and call the program\n"
            "with a threshold value below signal level and the\n"
            "expected delay time of ch.%d compared to ch.%d \n"
            "(positive or negative).\n"
            "Usage %s <threshold[V]> <delay[ps]>.\n\n", CH1, CH2, CH1, CH2, argv[0] );
    return 1;
  }

  sscanf( argv[1], "%lg", &threshold );
  sscanf( argv[2], "%d",  &delay2 );
  if ( delay2 < 0 ) {
    delay1 = -delay2;
    delay2 = 0;
  }
  return run( threshold, delay1, delay2 );
}
