"""Add ON DELETE CASCADE to all user foreign keys

Revision ID: cascade_delete_users
Revises: add_sms_notifs
Create Date: 2026-04-09
"""
from alembic import op

revision = "cascade_delete_users"
down_revision = "add_sms_notifs"
branch_labels = None
depends_on = None


def upgrade():
    constraints = [
        ("blog_comments_user_id_fkey", "blog_comments", "user_id"),
        ("blog_posts_user_id_fkey", "blog_posts", "user_id"),
        ("comments_user_id_fkey", "comments", "user_id"),
        ("communities_creator_id_fkey", "communities", "creator_id"),
        ("community_chat_messages_user_id_fkey", "community_chat_messages", "user_id"),
        ("community_events_user_id_fkey", "community_events", "user_id"),
        ("community_members_user_id_fkey", "community_members", "user_id"),
        ("community_project_tasks_assigned_to_user_id_fkey", "community_project_tasks", "assigned_to_user_id"),
        ("community_project_tasks_completed_by_user_id_fkey", "community_project_tasks", "completed_by_user_id"),
        ("community_project_tasks_creator_id_fkey", "community_project_tasks", "creator_id"),
        ("community_projects_creator_id_fkey", "community_projects", "creator_id"),
        ("conversation_users_user_id_fkey", "conversation_users", "user_id"),
        ("farm_game_states_user_id_fkey", "farm_game_states", "user_id"),
        ("food_inventory_user_id_fkey", "food_inventory", "user_id"),
        ("forge_pledges_user_id_fkey", "forge_pledges", "user_id"),
        ("forge_workers_user_id_fkey", "forge_workers", "user_id"),
        ("gardens_host_id_fkey", "gardens", "host_id"),
        ("grocery_lists_user_id_fkey", "grocery_lists", "user_id"),
        ("inbox_messages_user_id_fkey", "inbox_messages", "user_id"),
        ("join_requests_user_id_fkey", "join_requests", "user_id"),
        ("journal_entries_user_id_fkey", "journal_entries", "user_id"),
        ("node_membership_user_id_fkey", "node_membership", "user_id"),
        ("nodes_user_id_fkey", "nodes", "user_id"),
        ("payments_user_id_fkey", "payments", "user_id"),
        ("preforge_tags_user_id_fkey", "preforge_tags", "user_id"),
        ("preforge_topics_user_id_fkey", "preforge_topics", "user_id"),
        ("problem_notes_author_user_id_fkey", "problem_notes", "author_user_id"),
        ("project_tasks_assigned_user_id_fkey", "project_tasks", "assigned_user_id"),
        ("projects_user_id_fkey", "projects", "user_id"),
        ("ramblings_user_id_fkey", "ramblings", "user_id"),
        ("recipes_user_id_fkey", "recipes", "user_id"),
        ("resources_user_id_fkey", "resources", "user_id"),
        ("solution_notes_author_user_id_fkey", "solution_notes", "author_user_id"),
        ("stillness_checkins_user_id_fkey", "stillness_checkins", "user_id"),
        ("stillness_groups_created_by_fkey", "stillness_groups", "created_by"),
        ("stillness_members_user_id_fkey", "stillness_members", "user_id"),
        ("stillness_notification_prefs_user_id_fkey", "stillness_notification_prefs", "user_id"),
        ("stillness_notifications_sent_user_id_fkey", "stillness_notifications_sent", "user_id"),
        ("threads_user_id_fkey", "threads", "user_id"),
        ("transcription_usage_user_id_fkey", "transcription_usage", "user_id"),
        ("transcriptions_user_id_fkey", "transcriptions", "user_id"),
        ("user_categories_user_id_fkey", "user_categories", "user_id"),
        ("we_dream_entries_user_id_fkey", "we_dream_entries", "user_id"),
    ]

    for constraint_name, table_name, column_name in constraints:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table_name,
            "users",
            [column_name],
            ["id"],
            ondelete="CASCADE",
        )

    # forge_items keeps the post but nullifies the author reference
    op.drop_constraint("forge_items_created_by_user_id_fkey", "forge_items", type_="foreignkey")
    op.create_foreign_key(
        "forge_items_created_by_user_id_fkey",
        "forge_items",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    constraints = [
        ("blog_comments_user_id_fkey", "blog_comments", "user_id"),
        ("blog_posts_user_id_fkey", "blog_posts", "user_id"),
        ("comments_user_id_fkey", "comments", "user_id"),
        ("communities_creator_id_fkey", "communities", "creator_id"),
        ("community_chat_messages_user_id_fkey", "community_chat_messages", "user_id"),
        ("community_events_user_id_fkey", "community_events", "user_id"),
        ("community_members_user_id_fkey", "community_members", "user_id"),
        ("community_project_tasks_assigned_to_user_id_fkey", "community_project_tasks", "assigned_to_user_id"),
        ("community_project_tasks_completed_by_user_id_fkey", "community_project_tasks", "completed_by_user_id"),
        ("community_project_tasks_creator_id_fkey", "community_project_tasks", "creator_id"),
        ("community_projects_creator_id_fkey", "community_projects", "creator_id"),
        ("conversation_users_user_id_fkey", "conversation_users", "user_id"),
        ("farm_game_states_user_id_fkey", "farm_game_states", "user_id"),
        ("food_inventory_user_id_fkey", "food_inventory", "user_id"),
        ("forge_items_created_by_user_id_fkey", "forge_items", "created_by_user_id"),
        ("forge_pledges_user_id_fkey", "forge_pledges", "user_id"),
        ("forge_workers_user_id_fkey", "forge_workers", "user_id"),
        ("gardens_host_id_fkey", "gardens", "host_id"),
        ("grocery_lists_user_id_fkey", "grocery_lists", "user_id"),
        ("inbox_messages_user_id_fkey", "inbox_messages", "user_id"),
        ("join_requests_user_id_fkey", "join_requests", "user_id"),
        ("journal_entries_user_id_fkey", "journal_entries", "user_id"),
        ("node_membership_user_id_fkey", "node_membership", "user_id"),
        ("nodes_user_id_fkey", "nodes", "user_id"),
        ("payments_user_id_fkey", "payments", "user_id"),
        ("preforge_tags_user_id_fkey", "preforge_tags", "user_id"),
        ("preforge_topics_user_id_fkey", "preforge_topics", "user_id"),
        ("problem_notes_author_user_id_fkey", "problem_notes", "author_user_id"),
        ("project_tasks_assigned_user_id_fkey", "project_tasks", "assigned_user_id"),
        ("projects_user_id_fkey", "projects", "user_id"),
        ("ramblings_user_id_fkey", "ramblings", "user_id"),
        ("recipes_user_id_fkey", "recipes", "user_id"),
        ("resources_user_id_fkey", "resources", "user_id"),
        ("solution_notes_author_user_id_fkey", "solution_notes", "author_user_id"),
        ("stillness_checkins_user_id_fkey", "stillness_checkins", "user_id"),
        ("stillness_groups_created_by_fkey", "stillness_groups", "created_by"),
        ("stillness_members_user_id_fkey", "stillness_members", "user_id"),
        ("stillness_notification_prefs_user_id_fkey", "stillness_notification_prefs", "user_id"),
        ("stillness_notifications_sent_user_id_fkey", "stillness_notifications_sent", "user_id"),
        ("threads_user_id_fkey", "threads", "user_id"),
        ("transcription_usage_user_id_fkey", "transcription_usage", "user_id"),
        ("transcriptions_user_id_fkey", "transcriptions", "user_id"),
        ("user_categories_user_id_fkey", "user_categories", "user_id"),
        ("we_dream_entries_user_id_fkey", "we_dream_entries", "user_id"),
    ]

    for constraint_name, table_name, column_name in constraints:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        op.create_foreign_key(
            constraint_name, table_name, "users", [column_name], ["id"]
        )