from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '1024'
down_revision = 'f2243da90c2a'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('ml_predictions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('model_version', sa.String(20), nullable=False),
        sa.Column('appointment_id', sa.Integer(), sa.ForeignKey('appointments.id'), nullable=True),
        sa.Column('input_features', sa.JSON(), nullable=False),
        sa.Column('predicted_value', sa.Float(), nullable=False),
        sa.Column('actual_value', sa.Float(), nullable=True),
        sa.Column('predicted_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True)
    )
    op.create_index('ix_ml_predictions_model_name', 'ml_predictions', ['model_name'])
    op.create_index('ix_ml_predictions_predicted_at', 'ml_predictions', ['predicted_at'])

def downgrade():
    op.drop_table('ml_predictions')