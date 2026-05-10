%module(directors="1") tdapi

%pythonbegin %{
"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""
%}

%{
#include <iostream>
#include <string>
#include <boost/locale.hpp>
#include "ThostFtdcUserApiDataType.h"
#include "ThostFtdcUserApiStruct.h"
#include "ThostFtdcTraderApi.h"
%}

%feature("doxygen:ignore:system", range="line");
%feature("doxygen:ignore:company", range="line");
%feature("doxygen:ignore:history", range="line");
%feature("doxygen:ignore:file", range="line");
%feature("doxygen:alias:d{8}") "\d{8}"
%feature("doxygen:alias:d{4}") "\d{4}"
%feature("doxygen:alias:d{3}") "\d{3}"
%feature("doxygen:alias:d{1}") "\d{1}"

%feature("python:annotations", "c");
%feature("director") CThostFtdcTraderSpi;

%typemap(out) char[ANY], char[] {
    if ($1){
        if (!strlen($1)) {
            $result = SWIG_FromCharPtr("");
        } else {
            const std::string utf8_str = std::move(boost::locale::conv::to_utf<char>($1, "GBK"));
            $result = SWIG_FromCharPtrAndSize(utf8_str.c_str(),utf8_str.size());
        }
    }
}

%typemap(in) char *[] {
  /* Check if is a list */
  if (PyList_Check($input)) {
    int size = PyList_Size($input);
    int i = 0;
    $1 = (char **) malloc((size+1)*sizeof(char *));
    for (i = 0; i < size; i++) {
      PyObject *o = PyList_GetItem($input, i);
      if (PyUnicode_Check(o)) {
        $1[i] = (char *)PyUnicode_AsUTF8(o);
      } else {
        free($1);
        PyErr_SetString(PyExc_TypeError, "list must contain strings");
        SWIG_fail;
      }
    }
    $1[i] = 0;
  } else {
    PyErr_SetString(PyExc_TypeError, "not a list");
    SWIG_fail;
  }
}

// This cleans up the char ** array we malloc'd before the function call
%typemap(freearg) char ** {
  free((char *) $1);
}

%feature("director:except") {
  if ($error != NULL) {
    if (PyErr_ExceptionMatches(PyExc_SystemExit)) {
      throw Swig::DirectorMethodException("Exception: SystemExit");
    } else if (PyErr_ExceptionMatches(PyExc_SystemError)) {
      throw Swig::DirectorMethodException("Exception: SystemError");
    } else {
      PyErr_Print();
    }
  }
}

%include "ThostFtdcUserApiDataType.h"
%include "ThostFtdcUserApiStruct.h"
%include "ThostFtdcTraderApi.h"