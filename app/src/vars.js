/**
 * Different environment variables for dev/stage/prod.
 */


/* global process */
/* global module */

// eslint-disable-line no-undef
if (process.env.NODE_ENV === 'prod') {
  module.exports = {
    //API: 'https://b5ud8eqdja.execute-api.us-east-1.amazonaws.com/prod/api/v1/',
    tag: '<small>beta</small>'
  };
} else if (process.env.NODE_ENV === 'stage') {
  module.exports = {
    //API: 'https://m3a8w9y8f3.execute-api.us-east-1.amazonaws.com/stage/api/v1/',
    tag: '<big style="color:red">STAGING</big>'
  };
} else {
  module.exports = {
    //API: 'http://127.0.0.1:5000/api/v1/',
    tag: '<big style="color:red">DEV</big>'
  };
}
