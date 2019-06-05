// Copyright (c) Facebook, Inc. and its affiliates.
//
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

#include <istream>
#include <string>
#include <vector>

namespace binast {

// Reads a string table from |in|; sets the fail bit on error. Populates
// |strings|. As a side effect, this clears the ios_base::skipws flag on
// |in|.
std::istream& read_string_table(
     std::istream& in,
     std::vector<std::string>& strings,
     bool check_signature=false);
  
}
