# Debt Profile - Deployment Guide

## Overview
This guide covers the deployment process for the Debt Profile SaaS application.

## Prerequisites
- Docker and Docker Compose installed
- Domain name configured
- SSL certificate (Let's Encrypt recommended)
- Server with at least 2GB RAM, 2 CPU cores

## Environment Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/debt-profile.git
cd debt-profile
```

### 2. Environment Configuration
Create a `.env` file with production settings:

```env
DJANGO_SETTINGS_MODULE=_core.settings
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@localhost:5432/debtprofile

# Stripe Configuration
STRIPE_PUBLIC_KEY=pk_live_your_key_here
STRIPE_SECRET_KEY=sk_live_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

### 3. Database Setup
Update `docker-compose.yml` to use PostgreSQL in production:

```yaml
db:
  image: postgres:15
  environment:
    - POSTGRES_DB=debtprofile
    - POSTGRES_USER=debtprofile_user
    - POSTGRES_PASSWORD=secure_password_here
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

## Deployment Steps

### 1. Build and Start Services
```bash
# Build the application
docker-compose build

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec web python manage.py migrate

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

### 2. SSL Configuration
Set up SSL certificates using Let's Encrypt:

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 3. Nginx Configuration
Update `nginx.conf` for SSL:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # ... rest of configuration
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

## Monitoring and Maintenance

### Health Checks
- Application health: `https://yourdomain.com/api/schema/`
- Database connectivity: Check logs with `docker-compose logs db`

### Backup Strategy
```bash
# Database backup
docker-compose exec db pg_dump -U debtprofile_user debtprofile > backup_$(date +%Y%m%d_%H%M%S).sql

# Media files backup
tar -czf media_backup_$(date +%Y%m%d_%H%M%S).tar.gz media/
```

### Log Management
```bash
# View application logs
docker-compose logs -f web

# View nginx logs
docker-compose logs -f nginx

# View database logs
docker-compose logs -f db
```

## Scaling Considerations

### Horizontal Scaling
For high traffic, consider:
- Load balancer (nginx upstream)
- Redis for caching
- Multiple application instances
- Database read replicas

### Performance Optimization
- Enable gzip compression
- Set up CDN for static files
- Database query optimization
- Caching layer (Redis/Memcached)

## Security Checklist

- [ ] SSL/TLS enabled
- [ ] Strong SECRET_KEY configured
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS properly set
- [ ] Database credentials secured
- [ ] File permissions correct
- [ ] Regular security updates
- [ ] Firewall configured
- [ ] Backup strategy in place

## Troubleshooting

### Common Issues

1. **Application won't start**
   - Check logs: `docker-compose logs web`
   - Verify environment variables
   - Check database connectivity

2. **Static files not loading**
   - Run: `docker-compose exec web python manage.py collectstatic --noinput`
   - Check nginx configuration

3. **Database connection errors**
   - Verify database service is running: `docker-compose ps`
   - Check database credentials in environment

4. **SSL certificate issues**
   - Renew certificates: `sudo certbot renew`
   - Check certificate paths in nginx.conf

## Rollback Procedure

If deployment fails:

```bash
# Stop current deployment
docker-compose down

# Checkout previous version
git checkout <previous-commit-hash>

# Rebuild and restart
docker-compose build
docker-compose up -d
```

## Support

For deployment issues, check:
1. Application logs
2. Docker container status
3. Network connectivity
4. Resource usage (CPU, memory, disk)