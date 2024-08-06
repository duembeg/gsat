"""----------------------------------------------------------------------------
    version_info.py

    Copyright (C) 2013 Wilhelm Duembeg

    This file is part of gsat. gsat is a cross-platform GCODE debug/step for
    Grbl like GCODE interpreters. With features similar to software debuggers.
    Features such as breakpoint, change current program counter, inspection
    and modification of variables.

    gsat is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 2 of the License, or
    (at your option) any later version.

    gsat is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with gsat.  If not, see <http://www.gnu.org/licenses/>.

----------------------------------------------------------------------------"""

__all__ = [
    '__appname__',
    '__description__',

    # define authorship information
    '__authors__',
    '__author__',
    '__credits__',
    '__copyright__',
    '__license__',
    '__license_str__',

    # maintenance information
    '__maintainer__',
    '__email__',
    '__website__',

    # define version information
    '__requires__',
    '__version_info__',
    '__version__',
    '__revision__',
]

__appname__ = "Gcode Step and Alignment Tool"

__description__ = \
    "GCODE Step and Alignment Tool (gsat) is a cross-platform GCODE "\
    "debug/step for grbl like GCODE interpreters. With features similar "\
    "to software debuggers. Features Such as breakpoint, change current "\
    "program counter, inspection and modification of variables."


# define authorship information
__authors__ = ['Wilhelm Duembeg']
__author__ = ','.join(__authors__)
__credits__ = []
__copyright__ = 'Copyright (c) 2013 Wilhelm Duembeg'
__license__ = 'GPL v2, Copyright (c) 2013 Wilhelm Duembeg'
__license_str__ = __license__ + '\nhttp://www.gnu.org/licenses/gpl-2.0.txt'

# maintenance information
__maintainer__ = 'Wilhelm Duembeg'
__email__ = 'duembeg.github@gmail.com'
__website__ = 'https://github.com/duembeg/gsat'

# define version information
__requires__ = ['pySerial', 'wxPython']
__version_info__ = (1, 7, 5)
__version__ = 'v%i.%i.%i' % __version_info__
__revision__ = __version__
