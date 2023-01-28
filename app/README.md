# openelec-app
Frontend for openelec, lives at [rdrn.me/openelec](https://rdrn.me/openelec).  
Static site that interacts with [openelec](https://github.com/carderne/openelec) API running on Labda.

## Installation
Assumes the following are installed on your system.
 - [NodeJS](https://nodejs.org/en/download/) v10+ and npm
 - [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) for pushing to S3 bucket

Clone/download the project source and open the directory:
```
git clone https://github.com/carderne/openelec-app.git
cd openelec-app
```

Install global webpack and other dependencies:
```
sudo npm install -g webpack webpack-cli
npm install
```

## Usage
To compile in development mode run:
```
npm run dev
```
Output will be in `dist` subdirectory. Use [light-server](https://www.npmjs.com/package/light-server) as follows to serve locally:
```
npm install -g light-server
light-server -s dist
```

The `build.sh` script is included to automate compiling and uploading to AWS S3. First create a file called `config.yml` with the following format:
```
profile: <name of AWS CLI profile to use>
stage: s3://your.staging.bucket/
prod: s3://your.production.bucket/
```

Then the script can be used as follows:
```
./build.sh dev  # compile in development mode and serve locally
./build.sh stage   # compile in production mode and sync to S3 bucket
./build.sh prod    # ditto
```

## Development
All webpack compilation configuration is in `webpack.config.js`. Source files are in `src/`:
 - `index.js`: main app
 - `config.js`: run-time configuration, such as text and default values
 - `vars.js`: build-time configuration, such as API endpoint
 - `index.html` and `style.css`: all HTML and styling
 - additional assets in `src/favicon/`, `src/flags/`, `src/icons/` and `src/logo/`.
 - a few others (`sitemap.xml` etc) are in the project root directory and copied in by the build script

Main JavaScript dependencies are:
 - `jquery`
 - `d3`
 - `mapbox-gl`
 - `@mapbox/geojson-extent`
 - `osmtogeojson`
 - `bootstrap` and `bootstrap-slider`

It's a hand-coded SPA with all page structure in the HTML and _mostly_ logic in the JS.
