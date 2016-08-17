#!/usr/bin/env python3.4
#
#   Copyright 2016 - The Android Open Source Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import importlib

from acts.keys import Config

ACTS_CONTROLLER_CONFIG_NAME = "Attenuator"
ACTS_CONTROLLER_REFERENCE_NAME = "attenuators"

def create(configs, logger):
    objs = []
    for c in configs:
        attn_model = c["Model"]
        # Default to telnet.
        protocol = c.get("Protocol", "telnet")
        module_name = "acts.controllers.attenuator_lib.%s.%s" % (attn_model,
            protocol)
        module = importlib.import_module(module_name)
        inst_cnt = c["InstrumentCount"]
        attn_inst = module.AttenuatorInstrument(inst_cnt)
        attn_inst.model = attn_model
        insts = attn_inst.open(c[Config.key_address.value],
            c[Config.key_port.value])
        for i in range(inst_cnt):
            attn = Attenuator(attn_inst, idx=i)
            if "Paths" in c:
                try:
                    setattr(attn, "path", c["Paths"][i])
                except IndexError:
                    logger.error("No path specified for attenuator %d." % i)
                    raise
            objs.append(attn)
    return objs

def destroy(objs):
    return

r"""
Base classes which define how attenuators should be accessed, managed, and manipulated.

Users will instantiate a specific child class, but almost all operation should be performed
on the methods and data members defined here in the base classes or the wrapper classes.
"""


class AttenuatorError(Exception):
    r"""This is the Exception class defined for all errors generated by Attenuator-related modules.
    """
    pass


class InvalidDataError(AttenuatorError):
    r"""This exception is  thrown when an unexpected result is seen on the transport layer below
    the module.

    When this exception is seen, closing an re-opening the link to the attenuator instrument is
    probably necessary. Something has gone wrong in the transport.
    """
    pass


class InvalidOperationError(AttenuatorError):
    r"""Certain methods may only be accessed when the instance upon which they are invoked is in
    a certain state. This indicates that the object is not in the correct state for a method to be
    called.
    """
    pass


class AttenuatorInstrument(object):
    r"""This is a base class that defines the primitive behavior of all attenuator
    instruments.

    The AttenuatorInstrument class is designed to provide a simple low-level interface for
    accessing any step attenuator instrument comprised of one or more attenuators and a
    controller. All AttenuatorInstruments should override all the methods below and call
    AttenuatorInstrument.__init__ in their constructors. Outside of setup/teardown,
    devices should be accessed via this generic "interface".
    """
    model = None
    INVALID_MAX_ATTEN = 999.9

    def __init__(self, num_atten=0):
        r"""This is the Constructor for Attenuator Instrument.

        Parameters
        ----------
        num_atten : This optional parameter is the number of attenuators contained within the
        instrument. In some instances setting this number to zero will allow the driver to
        auto-determine, the number of attenuators; however, this behavior is not guaranteed.

        Raises
        ------
        NotImplementedError
            This constructor should never be called directly. It may only be called by a child.

        Returns
        -------
        self
            Returns a newly constructed AttenuatorInstrument
        """

        if type(self) is AttenuatorInstrument:
            raise NotImplementedError("Base class should not be instantiated directly!")

        self.num_atten = num_atten
        self.max_atten = AttenuatorInstrument.INVALID_MAX_ATTEN
        self.properties = None

    def set_atten(self, idx, value):
        r"""This function sets the attenuation of an attenuator given its index in the instrument.

        Parameters
        ----------
        idx : This zero-based index is the identifier for a particular attenuator in an
        instrument.
        value : This is a floating point value for nominal attenuation to be set.

        Raises
        ------
        NotImplementedError
            This constructor should never be called directly. It may only be called by a child.
        """
        raise NotImplementedError("Base class should not be called directly!")

    def get_atten(self, idx):
        r"""This function returns the current attenuation from an attenuator at a given index in
        the instrument.

        Parameters
        ----------
        idx : This zero-based index is the identifier for a particular attenuator in an instrument.

        Raises
        ------
        NotImplementedError
            This constructor should never be called directly. It may only be called by a child.

        Returns
        -------
        float
            Returns a the current attenuation value
        """
        raise NotImplementedError("Base class should not be called directly!")


class Attenuator(object):
    r"""This class defines an object representing a single attenuator in a remote instrument.

    A user wishing to abstract the mapping of attenuators to physical instruments should use this
    class, which provides an object that obscures the physical implementation an allows the user
    to think only of attenuators regardless of their location.
    """

    def __init__(self, instrument, idx=0, offset=0):
        r"""This is the constructor for Attenuator

        Parameters
        ----------
        instrument : Reference to an AttenuatorInstrument on which the Attenuator resides
        idx : This zero-based index is the identifier for a particular attenuator in an instrument.
        offset : A power offset value for the attenuator to be used when performing future
        operations. This could be used for either calibration or to allow group operations with
        offsets between various attenuators.

        Raises
        ------
        TypeError
            Requires a valid AttenuatorInstrument to be passed in.
        IndexError
            The index of the attenuator in the AttenuatorInstrument must be within the valid range.

        Returns
        -------
        self
            Returns a newly constructed Attenuator
        """
        if not isinstance(instrument, AttenuatorInstrument):
            raise TypeError("Must provide an Attenuator Instrument Ref")
        self.model = instrument.model
        self.instrument = instrument
        self.idx = idx
        self.offset = offset

        if(self.idx >= instrument.num_atten):
            raise IndexError("Attenuator index out of range for attenuator instrument")

    def set_atten(self, value):
        r"""This function sets the attenuation of Attenuator.

        Parameters
        ----------
        value : This is a floating point value for nominal attenuation to be set.

        Raises
        ------
        ValueError
            The requested set value+offset must be less than the maximum value.
        """

        if value+self.offset > self.instrument.max_atten:
            raise ValueError("Attenuator Value+Offset greater than Max Attenuation!")

        self.instrument.set_atten(self.idx, value+self.offset)

    def get_atten(self):
        r"""This function returns the current attenuation setting of Attenuator, normalized by
        the set offset.

        Returns
        -------
        float
            Returns a the current attenuation value
        """

        return self.instrument.get_atten(self.idx) - self.offset

    def get_max_atten(self):
        r"""This function returns the max attenuation setting of Attenuator, normalized by
        the set offset.

        Returns
        -------
        float
            Returns a the max attenuation value
        """
        if (self.instrument.max_atten == AttenuatorInstrument.INVALID_MAX_ATTEN):
            raise ValueError("Invalid Max Attenuator Value")

        return self.instrument.max_atten - self.offset


class AttenuatorGroup(object):
    r"""This is a handy abstraction for groups of attenuators that will share behavior.

    Attenuator groups are intended to further facilitate abstraction of testing functions from
    the physical objects underlying them. By adding attenuators to a group, it is possible to
    operate on functional groups that can be thought of in a common manner in the test. This
    class is intended to provide convenience to the user and avoid re-implementation of helper
    functions and small loops scattered throughout user code.

    """

    def __init__(self, name=""):
        r"""This is the constructor for AttenuatorGroup

        Parameters
        ----------
        name : The name is an optional parameter intended to further facilitate the passing of
        easily tracked groups of attenuators throughout code. It is left to the user to use the
        name in a way that meets their needs.

        Returns
        -------
        self
            Returns a newly constructed AttenuatorGroup
        """
        self.name = name
        self.attens = []
        self._value = 0

    def add_from_instrument(self, instrument, indices):
        r"""This function provides a way to create groups directly from the Attenuator Instrument.

        This function will create Attenuator objects for all of the indices passed in and add
        them to the group.

        Parameters
        ----------
        instrument : A ref to the instrument from which attenuators will be added
        indices : You pay pass in the indices either as a range, a list, or a single integer.

        Raises
        ------
        TypeError
            Requires a valid AttenuatorInstrument to be passed in.
        """

        if not instrument or not isinstance(instrument, AttenuatorInstrument):
            raise TypeError("Must provide an Attenuator Instrument Ref")

        if type(indices) is range or type(indices) is list:
            for i in indices:
                self.attens.append(Attenuator(instrument, i))
        elif type(indices) is int:
            self.attens.append(Attenuator(instrument, indices))

    def add(self, attenuator):
        r"""This function adds an already constructed Attenuator object to the AttenuatorGroup.

        Parameters
        ----------
        attenuator : An Attenuator object.

        Raises
        ------
        TypeError
            Requires a valid Attenuator to be passed in.
        """

        if not isinstance(attenuator, Attenuator):
            raise TypeError("Must provide an Attenuator")

        self.attens.append(attenuator)

    def synchronize(self):
        r"""This function can be called to ensure all Attenuators within a group are set
        appropriately.
        """

        self.set_atten(self._value)

    def is_synchronized(self):
        r"""This function queries all the Attenuators in the group to determine whether or not
        they are synchronized.

        Returns
        -------
        bool
            True if the attenuators are synchronized.
        """

        for att in self.attens:
            if att.get_atten() != self._value:
                return False
        return True

    def set_atten(self, value):
        r"""This function sets the attenuation value of all attenuators in the group.

        Parameters
        ----------
        value : This is a floating point value for nominal attenuation to be set.

        Returns
        -------
        bool
            True if the attenuators are synchronized.
        """

        value = float(value)
        for att in self.attens:
            att.set_atten(value)
        self._value = value

    def get_atten(self):
        r"""This function returns the current attenuation setting of AttenuatorGroup.

        This returns a cached value that assumes the attenuators are synchronized. It avoids a
        relatively expensive call for a common operation, and trusts the user to ensure
        synchronization.

        Returns
        -------
        float
            Returns a the current attenuation value for the group, which is independent of any
            individual attenuator offsets.
        """

        return float(self._value)
