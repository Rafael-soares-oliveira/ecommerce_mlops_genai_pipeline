import ibis
import ibis.expr.types as ir


def transform_users(users: ir.Table) -> ir.Table:
    """
    Aplica as transformações de negócio e tipagem.
    """
    users = users.mutate(
        id=users.id.cast("int32"),
        age=users.age.abs().fill_null(0).cast("int16"),
        gender=users.gender.fill_null("Others"),
        state=users.state.fill_null("Unknown"),
        city=users.city.fill_null("Unknown"),
        country=users.country.fill_null("Unknown"),
        traffic_source=users.traffic_source.fill_null("Unknown"),
        latitude=users.latitude.clip(-90, 90).fill_null(0.0),
        longitude=users.longitude.clip(-180, 180).fill_null(0.0),
    )

    users = users.mutate(
        context_summary=(
            ibis.literal("User profile: ")
            + users.gender
            + ", "
            + users.age.cast("string")
            + " years old, located_in "
            + users.city
            + ", "
            + users.state
            + ", "
            + users.country
            + ". Acquired via "
            + users.traffic_source
            + "."
        )
    )
    return users


def transform_distribution_centers(dc: ir.Table) -> ir.Table:
    """Aplica as transformações de negócio e tipagem."""
    # 1. Tipagem
    dc = dc.mutate(
        id=dc.id.cast("int32"),
    )

    # 2. Filtros
    dc = dc.mutate(
        latitude=dc.latitude.clip(-90, 90),
        longitude=dc.longitude.clip(-180, 180),
    )

    return dc


def transform_products(products: ir.Table) -> ir.Table:
    """Aplica as transformações de negócio e tipagem."""

    dc = products.mutate(
        id=products.id.cast("int32"),
        cost=products.cost.abs().round(2).cast("decimal(10,2)"),
        category=products.category.fill_null("Unknown"),
        name=products.name.fill_null("Unknown"),
        brand=products.brand.fill_null("Unknown"),
        retail_price=products.retail_price.abs().round(2).cast("decimal(10,2)"),
        department=products.department.fill_null("Unknown"),
        sku=products.sku.fill_null("Unknown"),
        distribution_center_id=products.distribution_center_id.cast("int16"),
    )

    return dc


def transform_inventory_items(ii: ir.Table) -> ir.Table:
    """Aplica as transformações de negócio e tipagem."""
    return ii.mutate(
        id=ii.id.cast("int32"),
        product_id=ii.product_id.cast("int32"),
        # created_at já costuma vir correto do parquet, mas garante-se:
        created_at=ii.created_at.cast("timestamp"),
        sold_at=ii.sold_at.cast("timestamp"),  # Pode ser nulo
        cost=ii.cost.abs().round(2).cast("decimal(10,2)"),
        product_category=ii.product_category.fill_null("Unknown"),
        product_name=ii.product_name.fill_null("Unknown"),
        product_brand=ii.product_brand.fill_null("Unknown"),
        product_retail_price=ii.product_retail_price.cast("decimal(10,2)"),
        product_department=ii.product_department.fill_null("Unknown"),
        product_sku=ii.product_sku.fill_null("Unknown"),
        product_distribution_center_id=ii.product_distribution_center_id.cast("int32"),
    )


def transform_orders(orders: ir.Table) -> ir.Table:
    df = orders.mutate(
        order_id=orders.order_id.cast("int32"),
        user_id=orders.user_id.cast("int32"),
        created_at=orders.created_at.cast("timestamp"),
        returned_at=orders.returned_at.cast("timestamp"),
        shipped_at=orders.shipped_at.cast("timestamp"),
        delivered_at=orders.delivered_at.cast("timestamp"),
        num_of_item=orders.num_of_item.cast("int16"),
    )
    df = df.mutate(
        shipped_at=(df.shipped_at < df.created_at).ifelse(df.created_at, df.shipped_at)
    )
    # Delivered não pode ser antes de Shipped
    df = df.mutate(
        delivered_at=(df.delivered_at < df.shipped_at).ifelse(
            df.shipped_at, df.delivered_at
        )
    )
    # Returned não pode ser antes de Delivered
    return df.mutate(
        returned_at=(df.returned_at < df.delivered_at).ifelse(
            df.delivered_at, df.returned_at
        )
    )


def transform_order_items(oi: ir.Table) -> ir.Table:
    df = oi.mutate(
        id=oi.id.cast("int32"),
        order_id=oi.order_id.cast("int32"),
        user_id=oi.user_id.cast("int32"),
        product_id=oi.product_id.cast("int32"),
        inventory_item_id=oi.inventory_item_id.cast("int32"),
        status=oi.status.fill_null("Processing"),
        created_at=oi.created_at.cast("timestamp"),
        shipped_at=oi.shipped_at.cast("timestamp"),
        delivered_at=oi.delivered_at.cast("timestamp"),
        returned_at=oi.returned_at.cast("timestamp"),
        sale_price=oi.sale_price.cast("decimal(10,2)"),
    )
    df = df.mutate(
        shipped_at=(df.shipped_at < df.created_at).ifelse(df.created_at, df.shipped_at)
    )
    df = df.mutate(
        delivered_at=(df.delivered_at < df.shipped_at).ifelse(
            df.shipped_at, df.delivered_at
        )
    )
    return df.mutate(
        returned_at=(df.returned_at < df.delivered_at).ifelse(
            df.delivered_at, df.returned_at
        )
    )
