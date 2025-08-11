# E-commerce Backend Documentation

## Overview

This Django-based e-commerce backend provides a robust RESTful API for managing products, categories, users, and addresses. The system is built using Django 5.2 with Django REST Framework (DRF) and follows the Model-Controller (MC) architectural pattern, where ViewSets act as Controllers. The View layer in the MVC pattern is represented by the frontend applications that consume this REST API.

## Architecture Overview

### Tech Stack
- **Framework**: Django 5.2 with Django REST Framework
- **Database**: PostgreSQL with Django ORM
- **Authentication**: JWT tokens via `django-rest-framework-simplejwt`
- **Additional Libraries**: 
  - `django-mptt` for hierarchical category trees
  - `django-cors-headers` for CORS handling
  - PostgreSQL-specific features for full-text search

### Project Structure
```
ecommerceBackend/
├── api/                          # API layer (Controllers & Serializers)
│   ├── controllers/              # ViewSets (Controllers)
│   ├── serializers.py           # Data serialization/validation
│   ├── urls.py                  # API route configuration
│   └── middleware.py            # Custom middleware
├── authentication/              # JWT authentication system
├── base/                        # Core models and utilities
│   ├── models/                  # Database models (Model layer)
│   ├── managers.py              # Custom model managers
│   ├── enums/                   # Application enums
│   └── abstractModels/          # Abstract base classes
└── ecommerceBackend/            # Django project settings
```

## Database Design & Models

The application uses Django's Object-Relational Mapping (ORM) to interact with a PostgreSQL database. Each model class represents a database table, with Django automatically handling the SQL generation and database operations.

### Core Models

#### 1. User Management
- **`UserModel`** (`base/models/user_model.py`)
  - Extends Django's `AbstractBaseUser` and `PermissionsMixin`
  - **Table**: `user`
  - **Key Fields**: UUID primary key, username, email, role (customer/seller/admin)
  - **Manager**: Custom `UserManager` for user creation logic
  - **Authentication**: Custom password hashing with pepper-based security

#### 2. Product Catalog
- **`CategoryModel`** (`base/models/category_model.py`)
  - Uses `django-mptt` for hierarchical tree structure
  - **Table**: `category`
  - **Key Features**: Self-referencing parent-child relationships, automatic slug generation
  - **Methods**: `get_ancestors()`, `get_descendants()` for tree traversal

- **`ProductModel`** (`base/models/product_model.py`)
  - **Table**: `product`
  - **Key Fields**: UUID primary key, name, description, images (PostgreSQL ArrayField), featured flag
  - **Relationships**: Foreign key to `CategoryModel`

- **`ProductItemModel`** (`base/models/product_item_model.py`)
  - **Table**: `productItem`
  - **Purpose**: Specific variants/SKUs of products with individual pricing and stock
  - **Key Fields**: SKU, stock, price, image URLs
  - **Relationships**: Foreign key to `ProductModel`

#### 3. Product Variations System
- **`VariationTypeModel`** (`base/models/variation_type_model.py`)
  - **Table**: `variationType`
  - **Purpose**: Defines types of variations (e.g., "Color", "Size")
  - **Relationships**: Optional foreign key to `CategoryModel`

- **`VariantModel`** (`base/models/variant_model.py`)
  - **Table**: `variant`
  - **Purpose**: Specific variation values (e.g., "Red", "Large")
  - **Relationships**: Foreign key to `VariationTypeModel`

- **`ProductConfigModel`** (`base/models/product_config_model.py`)
  - **Table**: `productConfig`
  - **Purpose**: Many-to-many relationship between `ProductItemModel` and `VariantModel`
  - **Constraints**: Unique together constraint on (productItem, variant)

#### 4. Address Management
- **`AddressModel`** (`base/models/address_model.py`)
  - **Table**: `address`
  - **Purpose**: Immutable address storage for order history and reuse
  - **Key Fields**: Address line, city, postcode, state, country

- **`UserAddressModel`** (`base/models/user_address_model.py`)
  - **Table**: `userAddress`
  - **Purpose**: Links users to addresses with default flag
  - **Relationships**: Foreign keys to `UserModel` and `AddressModel`
  - **Constraints**: Unique together constraint on (user, address)

## Architectural Pattern Implementation

### Models (M) - Data Layer
- **Location**: `base/models/`
- **Responsibility**: Data structure, business rules, database interactions
- **Features**:
  - Custom model managers (e.g., `UserManager`)
  - Model-level validation and constraints
  - Database-specific features (PostgreSQL arrays, full-text search)
  - MPTT for hierarchical data

### Controllers (ViewSets) - Business Logic Layer
- **Location**: `api/controllers/`
- **Technology**: Django REST Framework ViewSets
- **Responsibility**: HTTP request handling, business logic, response formatting, API endpoints
- **Implementation**: ViewSet methods + Serializers for data validation and transformation

#### Key Controllers:
1. **`UserViewSet`** (`api/controllers/user_view.py`)
   - CRUD operations for user management
   - Permission-based access control
   - Soft delete implementation

2. **`ProductViewSet`** (`api/controllers/product_view.py`)
   - Advanced product filtering (price, category, color, search)
   - Full-text search with PostgreSQL features
   - Pagination with custom `PagedList` class
   - Related product suggestions

3. **`CategoryViewSet`** (`api/controllers/category_view.py`)
   - Hierarchical category tree display
   - Optimized for tree structure rendering

4. **`AddressViewSet`** (`api/controllers/address_view.py`)
   - Address book management
   - Checkout address handling (guest and authenticated users)
   - Immutable address storage pattern

### Views (V) - Presentation Layer
- **Location**: External frontend application (React.js)
- **Responsibility**: User interface, user interactions, consuming the REST API
- **Note**: This backend provides the API endpoints that frontend applications use to render views

## Serializers - Data Transformation Layer

**Location**: `api/serializers.py`

Serializers handle the conversion between Python objects and JSON/API formats.

### Key Features:
- **Context-aware serialization**: Different fields for list vs. detail views
- **Method fields**: Dynamic data calculation (e.g., pricing, variations)
- **Nested relationships**: Automatic handling of foreign key relationships
- **Validation**: Field-level and object-level validation

## API Architecture & URL Routing

### URL Structure
```
/admin                          # Django admin interface
/auth/                         # Authentication endpoints
/api/                          # Main API endpoints
├── /user                      # User management
├── /product                   # Product catalog
│   ├── /featured             # Featured products
│   └── /{id}/related         # Related products
├── /category                  # Category hierarchy
└── /address                   # Address management
    └── /checkout             # Checkout-specific addresses
```

### Router Configuration
- **Technology**: Django REST Framework's `DefaultRouter`
- **Configuration**: No trailing slashes, automatic URL pattern generation
- **Registration**: ViewSets registered with router for automatic CRUD endpoint creation

## Advanced Features

### 1. Search Functionality
- **Full-text search**: PostgreSQL's `SearchVector` and `SearchQuery`
- **Fuzzy matching**: `TrigramSimilarity` for approximate matches
- **Weighted ranking**: Different weights for name vs. description matches
- **Fallback**: Basic `icontains` search when advanced features fail

### 2. Pagination
- **Custom Class**: `PagedList` extends DRF's `PageNumberPagination`
- **Features**: Configurable page size, comprehensive metadata in responses
- **Usage**: Automatic integration with ViewSet list methods

### 3. Hierarchical Categories
- **Technology**: `django-mptt` (Modified Preorder Tree Traversal)
- **Benefits**: Efficient tree queries, automatic tree maintenance
- **Features**: Ancestor/descendant retrieval, breadcrumb generation

### 4. Product Variations
- **Flexible System**: Support for any number of variation types per category
- **Many-to-many**: Products can have multiple variations (color + size)
- **Filtering**: Category-specific variation filtering in product queries

### 5. Address Management
- **Immutability**: Addresses are never modified, only new ones created
- **Deduplication**: Automatic reuse of identical addresses
- **Guest Support**: Checkout addresses for non-authenticated users
- **Default Handling**: Automatic default address management

## Database Configuration

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "ecommerce_db",
        "USER": "ecommerce_admin", 
        "PASSWORD": "capstone56",
        "HOST": "localhost",
        "PORT": "5432",
    }
}
```

### Key PostgreSQL Features Used:
- **ArrayField**: For storing multiple images and URLs
- **Full-text search**: Advanced search capabilities
- **Trigram similarity**: Fuzzy string matching
- **Tree queries**: Efficient hierarchical data handling via MPTT

## Security Features

### Authentication & Authorization
- **JWT Tokens**: Access and refresh token system
- **Custom Authentication**: `RefreshAuthentication` class
- **Permission Classes**: Role-based access control
- **CORS**: Configured for frontend integration

### Password Security
- **Custom Hasher**: `BCryptPepperHasher` with pepper-based security
- **Environment Variables**: Pepper stored securely
- **Fallback**: Standard Django password hashers as backup

### Data Protection
- **Soft Deletes**: User accounts deactivated rather than deleted
- **Immutable Records**: Address records preserved for audit trail
- **Validation**: Comprehensive input validation through serializers
