############################################################
#
#  Project:        quTAG User Library
#
#  Filename:       Makefile
#
#  Purpose:        GCC makefile for examples
#
#  Author:         N-Hands GmbH & Co KG
#
############################################################
# $Id: makefile.lx,v 1.1 2020/09/03 13:57:02 trurl Exp $

LIBDIR=../lib
INCDIR=../inc

TARGET=example0 example1 example2 example3 example4 example5 \
       example6 example7 example8

all : $(TARGET) libtdcbase.so

define outputrule
$(1): $(1:%=%.c)
	gcc -o $$@ -g -Wall -O0 -I$(INCDIR) -L$(LIBDIR) $$< -ltdcbase
endef
$(foreach src,$(TARGET),$(eval $(call outputrule,$(src))))

libtdcbase.so: ../lib/libtdcbase.so
	cp ../lib/libtdcbase.so .