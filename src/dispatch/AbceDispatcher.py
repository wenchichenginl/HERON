
# Copyright 2020, Battelle Energy Alliance, LLC
# ALL RIGHTS RESERVED
"""
  Interface for user-provided dispatching strategies.
"""
import os
import inspect
import numpy as np

from ravenframework.utils import utils, InputData, InputTypes
from .Dispatcher import Dispatcher
from .DispatchState import NumpyState

class Abce(Dispatcher):
  """
    Base class for strategies for consecutive dispatching in a continuous period.
  """
  # ---------------------------------------------
  # INITIALIZATION
  @classmethod
  def get_input_specs(cls):
    """
      Set acceptable input specifications.
      @ In, None
      @ Out, specs, InputData, specs
    """
    specs = InputData.parameterInputFactory('abce', ordered=False, baseNode=None)
    specs.addSub(InputData.parameterInputFactory('location', contentType=InputTypes.StringType,
        descr=r"""The hard drive location of the abce dispatcher. Paths are taken as absolue location. abce dispatchers must implement a \texttt{dispatch} method that accepts the HERON case, components, and sources; this method must return the activity for each resource of each component."""))
    specs.addSub(InputData.parameterInputFactory('settings_file', contentType=InputTypes.StringType,
        descr=r"""The hard drive location of the abce settings file. Paths are taken as absolue location."""))
    specs.addSub(InputData.parameterInputFactory('inputs_path', contentType=InputTypes.StringType,
        descr=r"""The hard drive location of the abce inputs. """))
    specs.addSub(InputData.parameterInputFactory('num_dispatch_years', contentType=InputTypes.IntegerType,
        descr=r"""The number of years to dispatch."""))
    specs.addSub(InputData.parameterInputFactory('num_repdays', contentType=InputTypes.IntegerType,
        descr=r"""The number of representative days to use for the dispatch."""))
    specs.addSub(InputData.parameterInputFactory('hist_wt', contentType=InputTypes.FloatType,
        descr=r"""The weight to give historical data."""))
    specs.addSub(InputData.parameterInputFactory('hist_decay', contentType=InputTypes.FloatType,
        descr=r"""The decay to give historical data."""))
    agent_opt=InputData.parameterInputFactory('agent_opt', ordered=False, 
        descr=r"""The optimization parameters for the agent.""")
    agent_opt.addSub(InputData.parameterInputFactory('consider_future_projects', contentType=InputTypes.BoolType,
        descr=r"""Whether to consider future projects."""))
    agent_opt.addSub(InputData.parameterInputFactory('num_future_periods_considered', contentType=InputTypes.IntegerType,
        descr=r"""The number of future periods to consider."""))
    agent_opt.addSub(InputData.parameterInputFactory('max_type_rets_per_pd', contentType=InputTypes.IntegerType,
        descr=r"""The maximum number of retirements per period."""))
    agent_opt.addSub(InputData.parameterInputFactory('max_type_newbuilds_per_pd', contentType=InputTypes.IntegerType,
        descr=r"""The maximum number of new builds per period."""))
    agent_opt.addSub(InputData.parameterInputFactory('shortage_protection_period', contentType=InputTypes.IntegerType,
        descr=r"""The number of periods to protect against shortage."""))
    agent_opt.addSub(InputData.parameterInputFactory('cap_decrease_threshold', contentType=InputTypes.FloatType,
        descr=r"""The capacity decrease threshold."""))
    agent_opt.addSub(InputData.parameterInputFactory('cap_decrease_margin', contentType=InputTypes.FloatType,
        descr=r"""The capacity decrease margin."""))
    agent_opt.addSub(InputData.parameterInputFactory('cap_maintain_threshold', contentType=InputTypes.FloatType,
        descr=r"""The capacity maintain threshold."""))
    agent_opt.addSub(InputData.parameterInputFactory('cap_maintain_margin', contentType=InputTypes.FloatType,
        descr=r"""The capacity maintain margin."""))
    agent_opt.addSub(InputData.parameterInputFactory('cap_increase_margin', contentType=InputTypes.FloatType,
        descr=r"""The capacity increase margin."""))
    agent_opt.addSub(InputData.parameterInputFactory('profit_lamda', contentType=InputTypes.FloatType,
        descr=r"""The profit lambda."""))
    agent_opt.addSub(InputData.parameterInputFactory('credit_rating_lamda', contentType=InputTypes.FloatType,
        descr=r"""The credit rating lambda."""))
    agent_opt.addSub(InputData.parameterInputFactory('cr_horizon', contentType=InputTypes.FloatType,
        descr=r"""The credit rating horizon."""))
    agent_opt.addSub(InputData.parameterInputFactory('int_bound', contentType=InputTypes.FloatType,
        descr=r"""The interest bound."""))
    specs.addSub(agent_opt)
    return specs

  def __init__(self):
    """
      Constructor.
      @ In, None
      @ Out, None
    """
    Dispatcher.__init__(self)
    self.name = 'AbceDispatcher'
    self._usr_loc = None # user-provided path to abce dispatcher module
    self._file = None    # resolved pathlib.Path to the abce dispatcher module
    self._disp_settings = {} # settings for the abce dispatcher
    self._agent_opt = {} # agent optimization settings

  def read_input(self, inputs):
    """
      Loads settings based on provided inputs
      @ In, inputs, InputData.InputSpecs, input specifications
      @ Out, None
    """
    usr_loc = inputs.findFirst('location')
    if usr_loc is None:
      if 'ABCE_DIR' not in os.environ:
        raise RuntimeError('ABCE environment variable not found. Please install ABCE and set the environment variable.')
      else:
        self._usr_loc = os.environ['ABCE_DIR']
        print(f'ABCE environment variable found at : {self._usr_loc}')
    else:
      self._usr_loc = usr_loc.value
    for sub in inputs.subparts:
      if sub.getName() == 'agent_opt':
        for opt in sub.subparts:
          self._agent_opt[opt.getName()] = opt.value
      else:
        self._disp_settings[sub.getName()] = sub.value
    print(f'Loaded abce dispatcher settings')
    print(f'Loaded abce agent optimization settings')



  def initialize(self, case, components, sources, **kwargs):
    """
      Initialize dispatcher properties.
      @ In, case, Case, HERON case instance
      @ In, components, list, HERON components
      @ In, sources, list, HERON sources
      @ In, kwargs, dict, keyword arguments
      @ Out, None
    """
    start_loc = case.run_dir
    file_loc = os.path.abspath(os.path.join(start_loc, self._usr_loc))
    # check that it exists
    if not os.path.isfile(file_loc):
      raise IOError(f'abce dispatcher not found at "{file_loc}"! (input dir "{start_loc}", provided path "{self._usr_loc}"')
    self._file = file_loc
    print(f'Loading abce dispatch at "{self._file}"')
    # load user module
    load_string, _ = utils.identifyIfExternalModelExists(self, self._file, '')
    module = utils.importFromPath(load_string, True)


  def dispatch(self, case, components, sources, meta):
    """
      Performs technoeconomic dispatch.
      @ In, case, Case, HERON case
      @ In, components, list, HERON components
      @ In, sources, list, HERON sources
      @ Out, results, dict, economic and production metrics
    """
    # load up time indices
    t_start, t_end, t_num = self.get_time_discr()
    time = np.linspace(t_start, t_end, t_num) # Note we don't care about segment/cluster here
    # load user module
    load_string, _ = utils.identifyIfExternalModelExists(self, self._file, '')
    module = utils.importFromPath(load_string, True)
    state = NumpyState()
    indexer = meta['HERON']['resource_indexer']
    state.initialize(components, indexer, time)
    # run dispatch
    results = module.dispatch(meta, state)
    # TODO: Check to make sure user has uploaded all activity data.
    return state


