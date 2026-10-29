# Generated for referral system

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='referral_code',
            field=models.CharField(blank=True, db_index=True, max_length=16, null=True, unique=True),
        ),
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('rewarded', models.BooleanField(default=False)),
                ('rewarded_at', models.DateTimeField(blank=True, null=True)),
                ('referrer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referrals_given', to='users.user')),
                ('referee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='referrals_received', to='users.user', unique=True)),
            ],
            options={
                'constraints': [
                    models.CheckConstraint(
                        condition=~models.Q(referrer=models.F('referee')),
                        name='referral_no_self_referral',
                    ),
                ],
            },
        ),
    ]
