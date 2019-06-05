// Copyright (c) Facebook, Inc. and its affiliates.
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

#include "string_table.h"

#include <string.h>

namespace binast {

std::istream& read_var_int(std::istream& in, size_t& i) {
  int shift = 0;
  i = 0;
  char ch;
  do {
    in >> ch;
    i |= (ch & 0x7f) << shift;
    shift += 7;
  } while (in && ch & 0x80);
  return in;
}

std::istream& read_string_table(
     std::istream& in,
     std::vector<std::string>& strings,
     bool check_signature) {
  std::noskipws(in);
  if (check_signature) {
    char signature[7] = { 0 };
    if (!in.read(signature, 7)) {
      return in;
    }
    if (strncmp("astdict", signature, 7)) {
      in.setstate(std::ios_base::failbit);
      return in;
    }
  }

  // Read the number of strings
  size_t num_strings;
  read_var_int(in, num_strings);

  // Read each string.
  std::vector<std::string>().swap(strings);
  strings.reserve(num_strings);
  for (auto i = 0; in && i < num_strings; i++) {
    std::string s;
    while (in) {
      char ch;
      in >> ch;
      if (ch == 0) {
	break;
      } else if (ch == 1 && in) {
	in >> ch;
      }
      s.push_back(ch);
    }
    strings.push_back(s);
  }
  return in;
}

}
