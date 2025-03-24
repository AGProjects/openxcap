"""initial_migration

Revision ID: 9662e80c6ac2
Revises: 
Create Date: 2025-03-11 16:45:10.460029

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = '9662e80c6ac2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('watchers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('presentity_uri', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('watcher_username', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('watcher_domain', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('event', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    sa.Column('inserted_time', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('presentity_uri', 'watcher_username', 'watcher_domain', 'event', name='watcher_idx')
    )
    op.create_table('xcap',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('domain', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('doc', sa.LargeBinary(), nullable=False),
    sa.Column('doc_type', sa.Integer(), nullable=False),
    sa.Column('etag', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('source', sa.Integer(), nullable=False),
    sa.Column('doc_uri', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('port', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username', 'domain', 'doc_type', 'doc_uri', name='account_doc_type_idx')
    )
    op.create_index('source_idx', 'xcap', ['source'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('xcap_subscriber_id_exists', table_name='xcap')
    op.drop_index('source_idx', table_name='xcap')
    op.drop_table('xcap')
    op.drop_table('watchers')
    # ### end Alembic commands ###
