# Copyright 2008 the V8 project authors. All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of Google Inc. nor the names of its
#       contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import test
import os
import subprocess
import shutil
from shutil import rmtree
from os import mkdir
from glob import glob
from os.path import join, dirname, exists
import re


FLAGS_PATTERN = re.compile(r"//\s+Flags:(.*)")
FILES_PATTERN = re.compile(r"//\s+Files:(.*)")

import json
def dump(obj, level=0):
   for attr in dir(obj):
     if hasattr( obj, attr ):
       print( "obj.%s = %s" % (attr, getattr(obj, attr)))

class PummelTestCase(test.TestCase):

  def __init__(self, path, file, mode, context, config, args):
    super(PummelTestCase, self).__init__(context, path, mode)
    self.file = file
    self.config = config
    self.mode = mode
    self.tmpdir = join(dirname(self.config.root), 'tmp')
    self.args = args

  def AfterRun(self, result):
    # delete the whole tmp dir
    try:
      rmtree(self.tmpdir)
    except:
      pass
    # make it again.
    try:
      mkdir(self.tmpdir)
    except:
      pass

  def BeforeRun(self):
    # delete the whole tmp dir
    try:
      rmtree(self.tmpdir)
    except:
      pass
    # make it again.
    # intermittently fails on win32, so keep trying
    while not os.path.exists(self.tmpdir):
      try:
        mkdir(self.tmpdir)
      except:
        pass
  
  def GetLabel(self):
    return "%s %s" % (self.mode, self.GetName())

  def GetName(self):
    return self.path[-1]

  def GetCommand(self):
    result = [self.config.context.GetVm(self.mode)]
    if self.file.endswith('.exe'):
      result = []
    else:
      if self.args and self.args.get("execArgv"):
        result.extend(self.args.get("execArgv").split(' '))

    if self.file:
      source = open(self.file).read()
      flags_match = FLAGS_PATTERN.search(source)
      if flags_match:
        result += flags_match.group(1).strip().split()
      files_match = FILES_PATTERN.search(source);
      additional_files = []
      if files_match:
        additional_files += files_match.group(1).strip().split()
      for a_file in additional_files:
        result.append(join(dirname(self.config.root), '..', a_file))
      result += [self.file]

    if self.args and self.args.get("argv"):
      result.extend(self.args.get("argv").split(' '))
    #print "\nresult", result
    return result

  def GetSource(self):
    return open(self.file).read()


class PummelTestConfiguration(test.TestConfiguration):

  def __init__(self, context, root):
    super(PummelTestConfiguration, self).__init__(context, root)

  def Ls(self, path):
    def SelectTest(name):
      return name.startswith('test-') and (name.endswith('.js') or name.endswith('.jx') or name.endswith('.exe'))
    return [f for f in os.listdir(path) if SelectTest(f)]

  def ListTests(self, current_path, path, mode):
    all_tests = [current_path + [t] for t in self.Ls(join(self.root))]
    result = []
    for test in all_tests:
      if self.Contains(path, test):
        file_path = join(self.root, reduce(join, test[1:], ""))

        self.argv = ""
        file_path_json = file_path + ".json"

        if exists(file_path_json):
          j = None
          try:
            j = json.loads(open(file_path_json).read());
          except:
            print "Cannot load json def: " + file_path_json

          deps = []

          if file_path.endswith('.js'):
            if j and j.get("dependencies"):
              deps = j.get("dependencies")
          else:
            if j and j.get("runtime_dependencies"):
              deps = j.get("runtime_dependencies")

          for dep in deps:
            args = json.loads( '{"argv" : "install ' + dep + '" }');
            dir = dirname(file_path)
            nd = join(dir, "node_modules")
            if not exists(nd):
              mkdir(nd)
            cwd = os.getcwd()
            fh = open("NUL","w")
            popen = subprocess.Popen( args = [ join(cwd, self.context.GetVm(mode)), 'install', dep ], cwd = dir, stdout = fh)
            popen.wait();
            fh.close()

          if j and j.get("args"):
            for argv in j["args"]:
              if file_path.endswith('.exe') and argv.get("execArgv") and argv.get("execArgv").startswith("mt"):
                # don't test native packages with mt/mt-keep
                continue

              repeat = self.context.repeat
              if repeat == 1 and argv.get("repeat"):
                try:
                  repeat = int(argv.get("repeat"))
                except:
                  print "The value for 'args[x].repeat' in json file is not a valid integer: " + file_path_json

              for i in range(0, repeat):
                result.append(PummelTestCase(test, file_path, mode, self.context, self, argv))
            continue

        for i in range(0, self.context.repeat):
          result.append(PummelTestCase(test, file_path, mode, self.context, self, None))
    return result

  def GetBuildRequirements(self):
    return ['sample', 'sample=shell']

  def GetTestStatus(self, sections, defs):
    status_file = join(self.root, 'pummel.status')
    if exists(status_file):
      test.ReadConfigurationInto(status_file, sections, defs)



def GetConfiguration(context, root):
  return PummelTestConfiguration(context, root)
