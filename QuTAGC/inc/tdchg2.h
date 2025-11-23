/******************************************************************************
 *
 *  Project:        TDC Control Library
 *
 *  Filename:       tdchg2.h
 *
 *  Purpose:        Heralded G(2) Functions
 *
 *  Author:         NHands GmbH & Co KG
 */
/*****************************************************************************/
/** @file tdchg2.h
 *  @brief Heralded g(2) Functions
 *
 *  The header provides functions to calculate "heralded g(2) functions"
 *  from TDC data. They are based on 3 signals: the "idler" and two 
 *  photo detectors.
 *
 *  Use the functions of @ref tdcbase.h to control the device. Set input
 *  channels parameters with @ref TDC_setHg2Params and @ref TDC_setHg2Input.
 *  Enable the collection of data with @ref TDC_enableHg2.
 *  When enabled, all incoming events on the selected channels contribute
 *  to the correlation functions. Use @ref TDC_calcHg2G2, @ref TDC_calcHg2Tcp,
 *  and @ref TDC_calcHg2Tcp1D to calculate g(2) functions and triple
 *  coincidence counts ("TCP").
 */
/*****************************************************************************/
/* $Id: tdchg2.h,v 1.2 2020/09/03 20:23:08 trurl Exp $ */

#ifndef __TDCHG2_H
#define __TDCHG2_H

#include "tdcdecl.h"


/** Enable HG2 Calculations
 *
 *  Enables the calculation of 2nd order cross correlation functions as the base
 *  of g(2) functions. When enabled, all incoming events on the selected
 *  TDC channels to the correlation functions.
 *  When disabled, all HG2 functions are unavailable.
 *  The function implicitly clears the correlation functions.
 *  Use @ref TDC_freezeBuffers to interrupt the accumulation of events without
 *  clearing the functions and  @ref TDC_resetHg2Correlations to clear without
 *  interrupt.
 *  @param enable  Enable or disable 
 *  @return        Error code
 */
TDC_API int TDC_CC TDC_enableHg2( Bln32 enable );


/** Set Correlation Function Parameters
 *
 *  Sets parameters for the correlation functions and g(2) functions.
 *  If the function is not called, default values are in place.
 *  When the function is called, all collected data are cleared.
 *  @param binWidth  Width of a bin in units of the TDC Time Base,
 *                   see @ref TDC_getTimebase . Range = 1 ... 1M, default = 1.
 *  @param binCount  Number of bins in the buffers.
 *                   Range = 16 ... 64k, default = 256.
 *  @return          Error code
 */
TDC_API int TDC_CC TDC_setHg2Params( Int32 binWidth,
                                     Int32 binCount );


/** Get Correlation Function Parameters
 *
 *  Retrieves the parameters set by @ref TDC_setHg2Params.
 *  @param binWidth  Output: Width of a bin in units of the TDC Time Base.
 *  @param binCount  Number of bins for the correlation functions.
 *                   g(2) functions will consist of 2*n-1 bins.
 *  @return          Error code
 */
TDC_API int TDC_CC TDC_getHg2Params( Int32 * binWidth,
                                     Int32 * binCount );


/** Set TDC Channels for Input
 *
 *  Sets the idler, the first and second input channel for correlation function calculation.
 *  If the function is not called, default values are in place.
 *  The function implicitly clears the correlation functions.
 *  @param idler     Idler  channel number, Range = 1...96, default = 1
 *  @param channel1  First  channel number, Range = 1...96, default = 2
 *  @param channel2  Second channel number, Range = 1...96, default = 3
 *  @return          Error code
 */
TDC_API int TDC_CC TDC_setHg2Input( Int32 idler,
                                    Int32 channel1,
                                    Int32 channel2 );


/** Get TDC Channels for Input
 *
 *  Retrieves the parameters set by @ref TDC_setHg2Input.
 *  All output parameters may be NULL to ignore the value.
 *  @param idler     Output: Idler  channel number
 *  @param channel1  Output: First  channel number
 *  @param channel2  Output: Second channel number
 *  @return          Error code
 */
TDC_API int TDC_CC TDC_getHg2Input( Int32 * idler,
                                    Int32 * channel1,
                                    Int32 * channel2 );


/** Reset Correlation Functions
 *
 *  Clears the accumulated correlation functions.
 *  @return  Error code
 */
TDC_API int TDC_CC TDC_resetHg2Correlations();


/** Calculate g(2) Function
 *
 *  Calculates the g(2) function based on the current state of the
 *  correlation functions.
 *  @param buffer   Output: g(2) function values.
 *                  An array of at least binCount elements must be provided.
 *  @param bufSize  Input: Number of elements of buffer
 *                  Output: Number of elements used (=binCount)
 *  @param reset    If the Correlation functions should be cleared after calculation
 *  @return         Error code
 */
TDC_API int TDC_CC TDC_calcHg2G2( double * buffer,
                                  Int32  * bufSize,
                                  Bln32    reset );


/** 2D triple coincidence count
 *
 *  Retreives the 2D triple coincidence count in an array of buffers.
 *  @param buffers  Output: two dimensional array of event counts.
 *                  buffers[a][b] will contain the number of triple coincidence
 *                  events with time differences a and b.
 *                  An array of at least binCount buffers with binCount elements must be provided.
 *  @param reset    If the histogram should be cleared after the call
 *  @return         Error code
 */
TDC_API int TDC_CC TDC_calcHg2Tcp( Int64 ** buffers,
                                   Bln32    reset );


/** 2D triple coincidence count - alternative interface
 *
 *  Retreives the 2D triple coincidence count in a single buffer.
 *  @param buffer   Output: array of event counts.
 *                  buffer[a + b * binCount] will contain the number of triple coincidence
 *                  events with time differences a and b.
 *                  An array of at least binCount^2 elements most be provided.
 *  @param  bufSize Input: Number of elements of buffer
 *                  Output: Number of elements used (=binCount^2)
 *  @param reset    If the histogram should be cleared after the call
 *  @return         Error code
 */
TDC_API int TDC_CC TDC_calcHg2Tcp1D( Int64 * buffer,
                                     Int32 * bufSize,
                                     Bln32   reset );
  

/** Raw counts
 *
 *  Retreives the raw histograms as counted for the g(2) function.
 *  All pointers may be NULL to ignore the corresponding values.
 *  @param evtIdler Output: Number of idler/trigger events registered and analyzed
 *  @param evtCoinc Output: Number of coincidences signal1 + idler with time diff < binwidth/2
 *  @param bufSsi   Output: Array of numbers of triple coincidences signal1 + signal2 + idler 
 *                  for every bin. The histogram is always centered around the zero-bin.
 *                  An array of at least binCount elements most be provided.
 *  @param bufS2i   Output: Array of numbers of coincidences signal2 and idler 
 *                  for every bin. The histogram is always centered around the zero-bin
 *                  An array of at least binCount elements most be provided.
 *  @param bufSize  Input: Number of elements of the buffers
 *                  Output: Number of elements used (=binCount)
 *  @return         Error code
 */
TDC_API int TDC_CC TDC_getHg2Raw( Int64 * evtIdler,
                                  Int64 * evtCoinc,
                                  Int64 * bufSsi,
                                  Int64 * bufS2i,
                                  Int32 * bufSize );


#endif
