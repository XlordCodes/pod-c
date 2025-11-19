from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64193863c50a'
down_revision: Union[str, Sequence[str], None] = 'f59a22dfbbcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema by adding nullable columns, migrating data, and applying constraints."""
    
    # 1. Add new columns as nullable=True (temporarily)
    op.add_column('bulk_jobs', sa.Column('template_name', sa.String(), nullable=True))
    op.add_column('bulk_jobs', sa.Column('language_code', sa.String(), nullable=True))
    op.add_column('bulk_jobs', sa.Column('components', sa.JSON(), nullable=True))
    
    # 2. Data Migration: Copy data from the old 'template' column and set defaults for new fields.
    #    We assume the old 'template' column holds the template name.
    op.execute(
        """
        UPDATE bulk_jobs 
        SET 
            template_name = template,
            language_code = 'en_US',
            components = '{}'::json
        WHERE template IS NOT NULL
        """
    )

    # 3. Alter columns to set NOT NULL constraints (now that data is present).
    op.alter_column('bulk_jobs', 'template_name',
               existing_type=sa.String(),
               nullable=False)
    op.alter_column('bulk_jobs', 'language_code',
               existing_type=sa.String(),
               server_default='en_US', # Sets a default for future rows
               nullable=False)
    
    # components remains nullable=True as per the model definition
    
    # 4. Drop the old column 'template'
    op.drop_column('bulk_jobs', 'template')


def downgrade() -> None:
    """Downgrade schema."""
    
    # 1. Add back the old 'template' column 
    op.add_column('bulk_jobs', sa.Column('template', sa.VARCHAR(), autoincrement=False, nullable=True))
    
    # 2. Transfer data back (optional)
    op.execute("UPDATE bulk_jobs SET template = template_name")
    
    # 3. Drop the new columns
    op.drop_column('bulk_jobs', 'components')
    op.drop_column('bulk_jobs', 'language_code')
    op.drop_column('bulk_jobs', 'template_name')
    
    # 4. Restore NOT NULL constraint on old column (if it was originally NOT NULL)
    op.alter_column('bulk_jobs', 'template', nullable=False)