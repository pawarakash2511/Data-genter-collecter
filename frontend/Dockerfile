FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/
COPY style.css  /usr/share/nginx/html/
COPY script.js  /usr/share/nginx/html/
COPY admin.html /usr/share/nginx/html/
COPY admin.js   /usr/share/nginx/html/

EXPOSE 80
