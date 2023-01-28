export const sliderConfigs = {
  'plan-nat': {
    'grid-dist': {
      'type': 'single',
      'default': '1',
      'label': 'Grid dist connected',
      'max': '5',
      'min': '0',
      'step': '0.5',
      'unit': 'km',
      'tooltip': 'Consider clusters within this distance as already connected.'
    },
    'demand-factor': {
      'type': 'single',
      'default': '5',
      'label': 'Demand factor',
      'max': '20',
      'min': '1',
      'step': '1',
      'unit': '',
      'tooltip': 'Demand factor in the formula demand=factor*log(gdp)'
    },
    'min-pop': {
      'type': 'single',
      'default': '100',
      'label': 'Minimum population',
      'max': '1000',
      'min': '0',
      'step': '50',
      'unit': '',
      'tooltip': 'Exclude from analysis villages with less that this population.'
    },
    'demand-ppm': {
      'type': 'single',
      'default': '6',
      'label': 'Demand',
      'max': '100',
      'min': '0',
      'step': '2',
      'unit': 'kWh/p/month',
      'tooltip': 'The average electricity demand per person in all clusters.'
    },
    'mg-gen-cost': {
      'type': 'single',
      'default': '4000',
      'label': 'Minigrid gen cost',
      'max': '10000',
      'min': '0',
      'step': '500',
      'unit': 'USD/kW',
      'tooltip': 'Installed cost of a minigrid system, excluding distribution.'
    },
    'mg-lv-cost': {
      'type': 'single',
      'default': '2',
      'label': 'Minigrid dist cost',
      'max': '10',
      'min': '0',
      'step': '1',
      'unit': 'USD/m2',
      'tooltip': 'Minigrid distribution cost as a function of village size.'
    },
    'grid-mv-cost': {
      'type': 'single',
      'default': '50',
      'label': 'Grid MV wire cost',
      'max': '200',
      'min': '0',
      'step': '10',
      'unit': 'USD/m',
      'tooltip': 'Grid MV lines extension cost.'
    },
    'grid-lv-cost': {
      'type': 'single',
      'default': '2',
      'label': 'Grid LV wire cost',
      'max': '10',
      'min': '0',
      'step': '1',
      'unit': 'USD/m2',
      'tooltip': 'Local in-cluster grid distribution cost as a function of village size.'
    },
  },
  'plan-loc': {
    'min-area': {
      'type': 'single',
      'default': '30',
      'label': 'Minimum building size',
      'max': '100',
      'min': '0',
      'step': '5',
      'unit': 'm2',
      'tooltip': 'Exclude from analysis buildings below this size.'
    },
    'demand': {
      'type': 'single',
      'default': '10',
      'label': 'Demand',
      'max': '100',
      'min': '0',
      'step': '2',
      'unit': 'kWh/person/month',
      'tooltip': 'Electricity demand per person.'
    },
    'tariff': {
      'type': 'single',
      'default': '0.5',
      'label': 'Tariff',
      'max': '1',
      'min': '0',
      'step': '0.05',
      'unit': 'USD/kWh',
      'tooltip': 'Tariff to be charged to consumers.'
    },
    'gen-cost': {
      'type': 'single',
      'default': '1000',
      'label': 'Generator cost',
      'max': '10000',
      'min': '0',
      'step': '500',
      'unit': 'USD/kW',
      'tooltip': 'Installed cost of a minigrid system, excluding distribution.'
    },
    'wire-cost': {
      'type': 'single',
      'default': '10',
      'label': 'Wire cost',
      'max': '50',
      'min': '0',
      'step': '5',
      'unit': 'USD/m',
      'tooltip': 'Cost of local distribution wires.'
    },
    'conn-cost': {
      'type': 'single',
      'default': '100',
      'label': 'Connection cost',
      'max': '500',
      'min': '0',
      'step': '20',
      'unit': 'USD/building',
      'tooltip': 'The connection cost per building.'
    },
    'opex-ratio': {
      'type': 'single',
      'default': '2',
      'label': 'OPEX ratio',
      'max': '10',
      'min': '0',
      'step': '1',
      'unit': '%',
      'tooltip': 'Annual operating costs as a percentage of CAPEX.'
    },
    'years': {
      'type': 'single',
      'default': '20',
      'label': 'Project life',
      'max': '30',
      'min': '0',
      'step': '1',
      'unit': 'years',
      'tooltip': 'Years over which to amortise project.'
    },
    'discount-rate': {
      'type': 'single',
      'default': '6',
      'label': 'Discount rate',
      'max': '20',
      'min': '0',
      'step': '1',
      'unit': '%',
      'tooltip': 'For calculating NPV.'
    }
  },
  'find-nat': {
    'pop-range': {
      'type': 'range',
      'default': '[0,1e14]',
      'label': 'Pop range',
      'max': '10000',
      'min': '0',
      'step': '100',
      'unit': '',
      'tooltip': 'Filter to clusters within this range.'
    },
    'grid-range': {
      'type': 'range',
      'default': '[0,1e14]',
      'label': 'Grid distance',
      'max': '40',
      'min': '0',
      'step': '1',
      'unit': 'km',
      'tooltip': 'Filter to clusters within this range.'
    },
    'ntl-range': {
      'type': 'range',
      'default': '[0.0,1e14]',
      'label': 'Night lights',
      'max': '1.0',
      'min': '0.0',
      'step': '0.1',
      'unit': '',
      'tooltip': 'Filter to clusters within this range.'
    },
    'gdp-range': {
      'type': 'range',
      'default': '[0,1e14]',
      'label': 'Economy',
      'max': '1000',
      'min': '0',
      'step': '100',
      'unit': 'USD/capita',
      'tooltip': 'Filter to clusters within this range.'
    },
    'travel-range': {
      'type': 'range',
      'default': '[0,1e14]',
      'label': 'Travel time',
      'max': '20',
      'min': '0',
      'step': '1',
      'unit': 'hours',
      'tooltip': 'Filter to clusters within this range.'
    },
  }
};

export const summaryConfigs = {
  'plan-nat': {
    'tot-cost': {
      'label': 'Total cost',
      'unit': 'USD'
    },
    'new-grid': {
      'label': 'New grid villages',
      'unit': ''
    },
    'new-off-grid': {
      'label': 'New off-grid villages',
      'unit': ''
    },
    'model-pop': {
      'label': 'Modelled pop',
      'unit': ''
    },
    'densify-pop': {
      'label': 'Densify pop',
      'unit': ''
    },
    'new-conn-pop': {
      'label': 'New grid pop',
      'unit': ''
    },
    'new-og-pop': {
      'label': 'Off-grid pop',
      'unit': ''
    }
  },
  'plan-loc': {
    'npv': {
      'label': 'NPV',
      'unit': 'USD'
    },
    'capex': {
      'label': 'CAPEX',
      'unit': 'USD'
    },
    'opex': {
      'label': 'OPEX',
      'unit': 'USD/year'
    },
    'income': {
      'label': 'Income',
      'unit': 'USD/year'
    },
    'connected': {
      'label': 'Connections',
      'unit': ''
    },
    'gen-size': {
      'label': 'Generator size',
      'unit': 'kW'
    },
    'line-length': {
      'label': 'Total line length',
      'unit': 'm'
    }
  },
  'find-nat': {
    'num-clusters': {
      'label': 'Clusters found',
      'unit': ''
    }
  }
};

export const countries = {
  'burundi': {
    'bounds': [[28.204503241, -4.525353124], [31.633190859, -2.279839647]],
    'pop': 10520000,
    'access-rate': 0.076,
    'access-urban': 0.497,
    'access-rural': 0.017
  },
  'ethiopia': {
    'bounds': [[32.627620026, -0.106069626], [48.332146354, 18.350369746]],
    'pop': 104900000,
    'access-rate': 0.429,
    'access-urban': 0.854,
    'access-rural': 0.265
  },
  'ghana': {
    'bounds': [[-3.906271679, 4.577887208], [1.842622619, 11.334163511]],
    'pop': 28830000,
    'access-rate': 0.793,
    'access-urban': 0.898,
    'access-rural': 0.666
  },
  'kenya': {
    'bounds': [[33.548264979, -4.964956591], [42.287539011, 5.305705381]],
    'pop': 49690000,
    'access-rate': 0.56,
    'access-urban': 0.776,
    'access-rural': 0.393
  },
  'lesotho': {
    // bounds are [W, S], [E, N]
    'bounds': [[27.0344, -30.3513], [29.1263, -28.5838]],
    'pop': 2233000,
    'access-rate': 0.297,
    'access-urban': 0.66,
    'access-rural': 0.157
  },
  'haiti': {
    'bounds': [[-74.4, 18], [-71.6, 20.1]],
    'pop': 10980000,
    'access-rate': 0.438,
    'access-urban': 0.782,
    'access-rural': 0.028
  },
  'rwanda': {
    'bounds': [[28.329516540, -2.884785794], [31.431263800, -1.002637116]],
    'pop': 12210000,
    'access-rate': 0.294,
    'access-urban': 0.8,
    'access-rural': 0.178
  },
  'senegal': {
    'bounds': [[-17.698204090, 10.674148389], [-11.187452269, 18.325782941]],
    'pop': 15850000,
    'access-rate': 0.645,
    'access-urban': 0.877,
    'access-rural': 0.383
  },
  'somalia': {
    'bounds': [[40.105438727, -1.987991680], [52.288756833, 12.330216161]],
    'pop': 14740000,
    'access-rate': 0.299,
    'access-urban': 0.572,
    'access-rural': 0.116
  },
  'tanzania': {
    'bounds': [[29.049252500, -12.376973616], [40.723047500, -0.354514384]],
    'pop': 56370000,
    'access-rate': 0.328,
    'access-urban': 0.653,
    'access-rural': 0.169
  },
  'zambia': {
    'bounds': [[21.706712241, -19.101743648], [33.998362069, -7.248606732]],
    'pop': 17090000,
    'access-rate': 0.272,
    'access-urban': 0.620,
    'access-rural': 0.027
  }
};

export const layerColors = {
  'grid': '#474747', // grey
  'clustersPlan': {
    'default': '#ffc14a', //orange
    'densify': '#377eb8', // blue
    'grid': '#4daf4a', // green
    'offgrid': '#e41a1c', // red
    'none': '#474747'  // grey
  },
  'clustersFind': {
    'default': '#ffc14a', //orange
    'top': '#49006a', // dark purplpe
    'bottom': '#fcc5c0' // light purple
  },
  'network': '#339900', // green
  'buildings': {
    'default': '#005824', // dark green
    'mg': '#43bcc6', // blue
    'shs': '#f97fac' // pink
  },
  'lv': '#4f5283' // grey
};
