from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    """E-Commerce Product Model supporting direct image uploads"""
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    category = models.CharField(max_length=100, default="General")
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, default="https://via.placeholder.com/300")
    created_at = models.DateTimeField(auto_now_add=True)

    def get_image_url(self):
        if self.image:
            return self.image.url
        return self.image_url or "https://via.placeholder.com/300"

    def __str__(self):
        return f"{self.brand} - {self.name} (${self.price})"


class Favorite(models.Model):
    """Stores user favorite products"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class Order(models.Model):
    """Stores user purchase history"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"


class ContactSubmission(models.Model):
    """Stores customer inquiries"""
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserInteractionLog(models.Model):
    """Tracks clicks, views, and interactions tied to session or logged-in user"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    session_id = models.CharField(max_length=100)
    page_url = models.CharField(max_length=200)
    action_type = models.CharField(max_length=50)
    element_id = models.CharField(max_length=100, blank=True, null=True)
    element_text = models.CharField(max_length=200, blank=True, null=True)
    product_id = models.IntegerField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)