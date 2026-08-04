"""create tax lots

Revision ID: eb3717d79960
Revises: b3a3a5836b80
Create Date: 2026-08-02 14:23:19.463726

"""
from typing import Sequence, Union

from alembic import op
from geoalchemy2 import Geometry
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb3717d79960'
down_revision: Union[str, Sequence[str], None] = 'b3a3a5836b80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create core.tax_lots
    op.create_table(
        "tax_lots",
        # Property Identity Columns
        sa.Column(
            "bbl",
            sa.Text(),
            nullable = False
        ),
        sa.Column(
            "borough_code",
            sa.SmallInteger(),
            nullable = False
        ),
        sa.Column(
            "borough",
            sa.Text(),
            nullable = False
        ),
        sa.Column(
            "tax_block",
            sa.Integer(),
            nullable = False
        ),
        sa.Column(
            "tax_lot",
            sa.Integer(),
            nullable = False 
        ),

        # Display and Classification Columns
        sa.Column(
            "address",
            sa.Text(),
            nullable = True
        ),
        sa.Column(
            "zip_code",
            sa.Text(),
            nullable = True
        ),
        sa.Column(
            "community_district",
            sa.SmallInteger(),
            nullable = True
        ),
        sa.Column(
            "building_class",
            sa.Text(),
            nullable = True
        ),
        sa.Column(
            "land_use",
            sa.Text(),
            nullable = True
        ),
        sa.Column(
            "owner_name",
            sa.Text(),
            nullable = True
        ),

        # Property Characteristics Columns
        sa.Column(
            "lot_area_sqft",
            sa.BigInteger(),
            nullable = True
        ),
        sa.Column(
            "building_area_sqft",
            sa.BigInteger(),
            nullable = True
        ),
        sa.Column(
            "number_of_buildings",
            sa.Integer(),
            nullable = True
        ),
        sa.Column(
            "number_of_floors",
            sa.Numeric(6, 2),
            nullable = True
        ),
        sa.Column(
            "residential_units",
            sa.Integer(),
            nullable = True
        ),
        sa.Column(
            "total_units",
            sa.Integer(),
            nullable = True
        ),
        sa.Column(
            "year_built",
            sa.SmallInteger(),
            nullable = True
        ),

        # Geography Columns
        sa.Column(
            "latitude",
            sa.Double(),
            nullable = True
        ),
        sa.Column(
            "longitude",
            sa.Double(),
            nullable = True
        ),
        sa.Column(
            "geom",
            Geometry(
                geometry_type = "MULTIPOLYGON",
                srid = 2263, 
                spatial_index = False
            ),
            nullable = False
        ),

        # Lineage Columns
        sa.Column(
            "pluto_version",
            sa.Text(),
            nullable = False
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone = True),
            nullable = False,
            server_default = sa.text("CURRENT_TIMESTAMP") 
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone = True),
            nullable = False,
            server_default = sa.text("CURRENT_TIMESTAMP") 
        ),
        sa.Column(
            "source_import_run_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "etl.import_runs.id",
                name="fk_tax_lots_source_import_run_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "bbl",
            name = "pk_tax_lots"
        ),
        sa.CheckConstraint(
            "bbl ~ '^[1-5][0-9]{9}$'",
            name = "ck_tax_lots_bbl_format"
        ),
        sa.CheckConstraint(
            """
            bbl =
                borough_code::text
                || lpad(tax_block::text, 5, '0')
                || lpad(tax_lot::text, 4, '0')
            """,
            name="ck_tax_lots_bbl_components_match",
        ),
        sa.CheckConstraint(
            "borough_code BETWEEN 1 AND 5",
            name = "ck_tax_lots_borough_code"
        ),
        sa.CheckConstraint(
            """
            borough IN (
                'MN',
                'BX',
                'BK',
                'QN',
                'SI'
            )
            """,
            name = "ck_tax_lots_borough"
        ),
        sa.CheckConstraint(
            """
            (borough_code = 1 AND borough = 'MN')
            OR (borough_code = 2 AND borough = 'BX')
            OR (borough_code = 3 AND borough = 'BK')
            OR (borough_code = 4 AND borough = 'QN')
            OR (borough_code = 5 AND borough = 'SI')
            """,
            name="ck_tax_lots_borough_matches_code",
        ),
        sa.CheckConstraint(
            "lot_area_sqft IS NULL OR lot_area_sqft >= 0",
            name="ck_tax_lots_lot_area_sqft_nonnegative",
        ),
        sa.CheckConstraint(
            "building_area_sqft IS NULL OR building_area_sqft >= 0",
            name="ck_tax_lots_building_area_sqft_nonnegative",
        ),
        sa.CheckConstraint(
            "number_of_buildings IS NULL OR number_of_buildings >= 0",
            name="ck_tax_lots_number_of_buildings_nonnegative",
        ),
        sa.CheckConstraint(
            "number_of_floors IS NULL OR number_of_floors >= 0",
            name="ck_tax_lots_number_of_floors_nonnegative",
        ),
        sa.CheckConstraint(
            "residential_units IS NULL OR residential_units >= 0",
            name="ck_tax_lots_residential_units_nonnegative",
        ),
        sa.CheckConstraint(
            "total_units IS NULL OR total_units >= 0",
            name="ck_tax_lots_total_units_nonnegative",
        ),
        sa.CheckConstraint(
            "tax_block >= 0",
            name="ck_tax_lots_tax_block_nonnegative",
        ),
        sa.CheckConstraint(
            "tax_lot >= 0",
            name="ck_tax_lots_tax_lot_nonnegative",
        ),
        sa.CheckConstraint(
            "char_length(btrim(pluto_version)) > 0",
            name = "ck_tax_lots_pluto_version_not_blank"
        ),
        sa.CheckConstraint(
            "year_built IS NULL OR year_built BETWEEN 1600 AND 2100",
            name="ck_tax_lots_year_built_range",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_tax_lots_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_tax_lots_longitude_range",
        ),
        schema = "silver"
    )

    op.create_index(
        "ix_tax_lots_geom",
        "tax_lots",
        ["geom"],
        unique = False,
        postgresql_using = "GIST",
        schema = "silver"
    )

    op.create_index(
        "ix_tax_lots_source_import_run_id",
        "tax_lots",
        ["source_import_run_id"],
        unique = False,
        schema = "silver"
    )
    pass


def downgrade() -> None:
    op.drop_index(
        "ix_tax_lots_source_import_run_id",
        table_name="tax_lots",
        schema="silver",
    )

    op.drop_index(
        "ix_tax_lots_geom",
        table_name="tax_lots",
        schema="silver",
    )

    op.drop_table(
        "tax_lots",
        schema="silver",
    )
    pass
