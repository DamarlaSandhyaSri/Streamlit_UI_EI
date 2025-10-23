import streamlit as st
import pandas as pd
from datetime import datetime
import json
from typing import Optional
from dynamo import DynamoDBClient
from query_generator import QueryGenerator
from logger import get_logger
from concern_risk_misc_naics import concerns_events, emerging_risks, misc_topics, naics_data
import streamlit.components.v1 as components

logger = get_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="Emerging Insights Query System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS for card-based layout
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stats-box {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 10px 0;
        height: 180px
    }
    .query-explanation {
        background-color: #e8f4f8;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #2196F3;
        margin: 15px 0;
        font-size: 0.9rem;
    }
    .article-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .article-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        transform: translateY(-2px);
    }
    .article-title {
        font-size: 1.3rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 10px;
        line-height: 1.4;
    }
    .article-summary {
        color: #555;
        font-size: 0.95rem;
        line-height: 1.6;
        margin-bottom: 15px;
    }
    .article-meta {
        display: flex;
        gap: 15px;
        flex-wrap: wrap;
        margin-bottom: 10px;
        font-size: 0.85rem;
    }
    .meta-item {
        background: #f5f5f5;
        padding: 5px 10px;
        border-radius: 5px;
        color: #666;
    }
    .tag-current {
        background-color: #4CAF50;
        color: white;
        padding: 5px 12px;
        border-radius: 5px;
        font-weight: bold;
        display: inline-block;
    }
    .tag-trend {
        background-color: #FF9800;
        color: white;
        padding: 5px 12px;
        border-radius: 5px;
        font-weight: bold;
        display: inline-block;
    }
    .tag-untagged {
        background-color: #9E9E9E;
        color: white;
        padding: 5px 12px;
        border-radius: 5px;
        font-weight: bold;
        display: inline-block;
    }
    .tag-error {
        background-color: #F44336;
        color: white;
        padding: 5px 12px;
        border-radius: 5px;
        font-weight: bold;
        display: inline-block;
    }
    .expand-btn {
        background-color: #1f77b4;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 5px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: background-color 0.3s;
    }
    .expand-btn:hover {
        background-color: #155a8a;
    }
    .full-content {
        background: #f9f9f9;
        padding: 20px;
        border-radius: 8px;
        margin-top: 15px;
        border-left: 4px solid #1f77b4;
    }
    .filter-section {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .concern-badge {
        background: #e3f2fd;
        color: #1976d2;
        padding: 4px 10px;
        border-radius: 4px;
        margin: 3px;
        display: inline-block;
        font-size: 0.85rem;
    }
    .risk-badge {
        background: #fff3e0;
        color: #f57c00;
        padding: 4px 10px;
        border-radius: 4px;
        margin: 3px;
        display: inline-block;
        font-size: 0.85rem;
    }
    /* Target the expander summary text */
    div > div[data-testid="stMarkdownContainer"] > p {
        color: #1E90FF;      /* Your desired color */
        font-size: 18px;      /* Your desired font size */
    }

    /* Optional: change hover color for expander header */
    div > div[data-testid="stMarkdownContainer"] > p:hover {
        color: #2832C0;
    }
</style>
""", unsafe_allow_html=True)


class InsuranceQueryApp:
    def __init__(self):
        self.initialize_session_state()
        self.dynamo_client = DynamoDBClient()
        self.query_generator = QueryGenerator()
    
    def initialize_session_state(self):
        """Initialize session state variables."""
        if 'query_results' not in st.session_state:
            st.session_state.query_results = None
        if 'query_history' not in st.session_state:
            st.session_state.query_history = []
        if 'last_query' not in st.session_state:
            st.session_state.last_query = ""
        if 'expanded_articles' not in st.session_state:
            st.session_state.expanded_articles = set()
    
    def execute_dynamodb_query(self, query_params: dict) -> Optional[list]:
        """Execute the DynamoDB query based on generated parameters."""
        try:
            table = self.dynamo_client.table
            scan_kwargs = {}
            
            if query_params.get("filter_expression"):
                scan_kwargs["FilterExpression"] = query_params["filter_expression"]
            
            if query_params.get("expression_attribute_names") and query_params.get("filter_expression"):
                scan_kwargs["ExpressionAttributeNames"] = query_params["expression_attribute_names"]
            
            if query_params.get("expression_attribute_values") and query_params.get("filter_expression"):
                attr_values = {}
                for key, value in query_params["expression_attribute_values"].items():
                    attr_values[key] = value
                scan_kwargs["ExpressionAttributeValues"] = attr_values
            
            if query_params.get("limit"):
                scan_kwargs["Limit"] = query_params["limit"]
            
            if query_params["query_type"] == "query" and query_params.get("partition_key"):
                from boto3.dynamodb.conditions import Key
                pk = query_params["partition_key"]
                scan_kwargs["KeyConditionExpression"] = Key(pk["name"]).eq(pk["value"])
                response = table.query(**scan_kwargs)
            else:
                response = table.scan(**scan_kwargs)
            
            items = response.get('Items', [])
            
            while 'LastEvaluatedKey' in response and len(items) < query_params.get("limit", 100):
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                response = table.scan(**scan_kwargs)
                items.extend(response.get('Items', []))
            
            logger.info(f"Query returned {len(items)} items")
            return items
            
        except Exception as e:
            logger.error(f"Error executing DynamoDB query: {e}")
            st.error(f"Error executing query: {str(e)}")
            return None
    
    def format_tag(self, tag: str) -> str:
        """Format tag with appropriate styling."""
        if not tag:
            return '<span class="tag-untagged">Untagged</span>'
        
        tag_classes = {
            "Current": "tag-current",
            "Potential New Trend": "tag-trend",
            "Untagged": "tag-untagged",
            "Processing Error": "tag-error"
        }
        
        css_class = tag_classes.get(tag, "tag-untagged")
        return f'<span class="{css_class}">{tag}</span>'

    def render_article_card(self, article: dict, index: int):
        """Render individual article card with collapsible/expandable functionality."""
        article_id = f"article_{index}"
        is_expanded = article_id in st.session_state.expanded_articles

        # Extract article data
        title = str(article.get('Title') or 'Untitled Article')[:200]
        summary = article.get('ReasonIdentified', article.get('Description', 'No summary available'))[:300]
        source = article.get('Source', 'Unknown Source')
        tag = article.get('Tag', 'Untagged')
        url = article.get('URL', '#')
        concerns = article.get('Concerns', '').split(';') if article.get('Concerns') else []
        risks = article.get('EmergingRiskName', '').split(';') if article.get('EmergingRiskName') else []
        date_time = article.get('DateTime', 'Unknown Date')

        # Build badges HTML
        badges_html = ""
        if concerns and concerns[0]:
            badges_html += "<div style='margin-top: 10px;'>"
            for concern in concerns[:5]:
                if concern.strip():
                    badges_html += f'<span class="concern-badge">🚨 {concern.strip()}</span>'
            badges_html += "</div>"

        if risks and risks[0]:
            badges_html += "<div style='margin-top: 5px;'>"
            for risk in risks[:5]:
                if risk.strip():
                    badges_html += f'<span class="risk-badge">⚠️ {risk.strip()}</span>'
            badges_html += "</div>"

        # Use st.expander for the whole card
        with st.expander(f"{title} ({date_time[:10] if date_time != 'Unknown Date' else date_time})", expanded=False):
            # Article meta
            st.markdown(f"""
            <div class="article-meta">
                <span class="meta-item">📰 {source}</span>
                <span>{self.format_tag(tag)}</span>
            </div>
            <div class="article-summary">{summary}{'...' if len(summary) >= 300 else ''}</div>
            {badges_html}
            """, unsafe_allow_html=True)

            # Buttons for source & copy link
            col1, col2 = st.columns([1,1])
            with col2:
                if url and url != '#':
                    import streamlit.components.v1 as components
                    components.html(f"""
                    <div style="display: flex; gap: 5px; align-items: center;">
                        <a href="{url}" target="_blank" style="text-decoration: none;">
                            <button style="background-color: #4CAF50; color: white; padding: 5px 12px; border-radius: 5px; font-weight: bold; display: inline-block;">🔗 Source</button>
                        </a>
                        <button style="background-color: #4CAF50; color: white; padding: 5px 12px; border-radius: 5px; font-weight: bold; display: inline-block;" onclick="
                            navigator.clipboard.writeText('{url}').then(() => {{
                                const original = this.innerText;
                                this.innerText = '✅ Copied';
                                setTimeout(() => this.innerText = original, 1500);
                            }})
                        ">📋 Copy</button>
                    </div>
                    """, height=50)

            # Full details inside the expander
            st.markdown('<div class="full-content">', unsafe_allow_html=True)
            st.markdown("### 📄 Full Article Content")
            full_data = article.get('Data', 'No full content available')
            st.text_area("Full Article Content", value=full_data, height=200, key=f"content_{article_id}", label_visibility="collapsed")

            # Additional metadata
            st.markdown("### 📊 Classification Details")
            col1, col2 = st.columns(2)
            with col1:
                if concerns and concerns[0]:
                    st.markdown("**Concerns:**")
                    for concern in concerns:
                        if concern.strip():
                            st.write(f"• {concern.strip()}")
                if article.get('MiscTopics'):
                    topics = article.get('MiscTopics', '').split(';')
                    st.markdown("**Misc Topics:**")
                    for topic in topics:
                        if topic.strip():
                            st.write(f"• {topic.strip()}")
            with col2:
                if risks and risks[0]:
                    st.markdown("**Emerging Risks:**")
                    for risk in risks:
                        if risk.strip():
                            st.write(f"• {risk.strip()}")
                if article.get('NAICSCODE'):
                    st.markdown("**NAICS:**")
                    st.write(f"• Code: {article.get('NAICSCODE')}")
                    st.write(f"• {article.get('NAICSDescription', 'N/A')}")
            st.markdown('</div>', unsafe_allow_html=True)


    def display_results(self, results: list):
        """Display query results in card format."""
        if not results:
            st.warning("No results found for your query.")
            return
        
        df = pd.DataFrame(results)
        
        # Display statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="stats-box">
                <h2 style="margin:0; color:#1f77b4; height:100px">Total Records</h2>
                <h3> {len(df)} </h3>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            current_count = len(df[df.get('Tag', '') == 'Current']) if 'Tag' in df.columns else 0
            st.markdown(f"""
            <div class="stats-box">
                <h2 style="margin:0; color:#4CAF50; height:100px">Current</h2>
                <h3> {current_count} </h3>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            trend_count = len(df[df.get('Tag', '') == 'Potential New Trend']) if 'Tag' in df.columns else 0
            st.markdown(f"""
            <div class="stats-box">
                <h2 style="margin:0; color:#FF9800; height:100px">New Trends</h2>
                <h3> {trend_count} </h3>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            untagged_count = len(df[df.get('Tag', '').isin(['Untagged', '', None])]) if 'Tag' in df.columns else 0
            st.markdown(f"""
            <div class="stats-box">
                <h2 style="margin:0; color:#9E9E9E; height:100px">Untagged</h2>
                <h3> {untagged_count} </h3>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Filters
        st.markdown('<div class="filter-section">', unsafe_allow_html=True)
        st.markdown("### Filter Results")
        
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
        
        with filter_col1:
            if 'Tag' in df.columns:
                tag_filter = st.multiselect(
                    "Filter by Tag:",
                    options=df['Tag'].unique().tolist(),
                    key="tag_filter"
                )
                if tag_filter:
                    df = df[df['Tag'].isin(tag_filter)]
        
        with filter_col2:
            if 'Source' in df.columns:
                source_filter = st.multiselect(
                    "Filter by Source:",
                    options=df['Source'].dropna().unique().tolist(),
                    key="source_filter"
                )
                if source_filter:
                    df = df[df['Source'].isin(source_filter)]
        
        with filter_col3:
            sort_by = st.selectbox(
                "Sort by:",
                options=["Most Recent", "Title A-Z", "Source"],
                key="sort_option"
            )
        
        with filter_col4:
            items_per_page = st.selectbox(
                "Items per page:",
                options=[10, 20, 50, 100],
                index=1,
                key="items_per_page"
            )
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Apply sorting
        if sort_by == "Most Recent" and 'DateTime' in df.columns:
            df = df.sort_values('DateTime', ascending=False)
        elif sort_by == "Title A-Z" and 'Title' in df.columns:
            df = df.sort_values('Title')
        elif sort_by == "Source" and 'Source' in df.columns:
            df = df.sort_values('Source')
        
        # Pagination
        total_items = len(df)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 1
        
        # Display articles
        st.markdown(f"### 📋 Showing {min(items_per_page, total_items)} of {total_items} articles")
        
        start_idx = (st.session_state.current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        
        # Render article cards
        for idx in range(start_idx, end_idx):
            self.render_article_card(df.iloc[idx].to_dict(), idx)
        
        # Pagination controls
        if total_pages > 1:
            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            
            with col1:
                if st.button("⏮️ First", disabled=st.session_state.current_page == 1):
                    st.session_state.current_page = 1
                    st.rerun()
            
            with col2:
                if st.button("◀️ Previous", disabled=st.session_state.current_page == 1):
                    st.session_state.current_page -= 1
                    st.rerun()
            
            with col3:
                st.markdown(f"<p style='text-align: center'>Page {st.session_state.current_page} of {total_pages}</p>", unsafe_allow_html=True)
            
            with col4:
                if st.button("Next ▶️", disabled=st.session_state.current_page == total_pages):
                    st.session_state.current_page += 1
                    st.rerun()
            
            with col5:
                if st.button("Last ⏭️", disabled=st.session_state.current_page == total_pages):
                    st.session_state.current_page = total_pages
                    st.rerun()
        
        # Download options
        st.markdown("---")
        st.markdown("### 💾 Export Data")
        col1, col2 = st.columns(2)
        
        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"insurance_query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            json_str = df.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download as JSON",
                data=json_str,
                file_name=f"insurance_query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    def render_sidebar(self):
        """Render sidebar with query examples and reference data."""
        st.sidebar.title("Query Assistant")
        
        st.sidebar.markdown("### 📊 Example Queries")
        
        if st.sidebar.button("📊 Show All Articles", key="show_all", type="primary"):
            st.session_state.last_query = "show all articles"
            st.session_state.current_page = 1
            st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("**FAQs:**")
        
        examples = [
            "Show all articles tagged as Current",
            "Find articles about Climate Change",
            "Show articles with lawsuits or property damage concerns",
            "Find Potential New Trend articles about PFAS",
            "Show articles from Construction Industry",
            "Find articles about ransomware and cyber attacks",
            "Show untagged articles",
            "Find articles about electric vehicles",
            "Show articles with NAICS code 524126"
        ]
        
        for i, example in enumerate(examples):
            if st.sidebar.button(example, key=f"example_{i}"):
                st.session_state.last_query = example
                st.session_state.current_page = 1
                st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📚 Reference Data")
        
        with st.sidebar.expander("🚨 Concerns Available"):
            st.write(", ".join(concerns_events[:20]) + "...")
            
        with st.sidebar.expander("⚠️ Emerging Risks Available"):
            st.write(", ".join(emerging_risks[:20]) + "...")
        
        with st.sidebar.expander("📌 Misc Topics Available"):
            st.write(", ".join(misc_topics))
        
        with st.sidebar.expander("🏭 NAICS Codes"):
            st.write(f"Total codes available: {len(naics_data)}")
            st.write("Sample:", ", ".join([f"{n['code']}" for n in naics_data[:5]]) + "...")
    
    def run(self):
        """Main application loop."""
        st.markdown('<h1 class="main-header"> Emerging Insights Query System</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">Search and analyze insurance-related articles using natural language queries</p>', unsafe_allow_html=True)
        
        self.render_sidebar()
        
        # st.markdown("### Enter Your Query")
        
        query_input = st.text_area(
            "Describe what you're looking for:",
            value=st.session_state.last_query,
            height=100,
            placeholder="Example: Show me all articles about climate change with property damage concerns..."
        )
        
        col1, col2, col3 = st.columns([1, 1, 3])
        
        with col1:
            search_button = st.button("🔎 Search", type="primary")
        
        with col2:
            clear_button = st.button("🗑️ Clear")
        
        if clear_button:
            st.session_state.last_query = ""
            st.session_state.query_results = None
            st.session_state.current_page = 1
            st.session_state.expanded_articles = set()
            st.rerun()
        
        if search_button and query_input.strip():
            with st.spinner("🤖 Generating and executing query..."):
                query_params = self.query_generator.generate_query(query_input)
                
                # if query_params.get("explanation"):
                #     st.markdown(f"""
                #     <div class="query-explanation">
                #         <strong>🎯 Query Understanding:</strong> {query_params['explanation']}
                #     </div>
                #     """, unsafe_allow_html=True)
                
                # with st.expander("🔧 Technical Query Details"):
                #     st.json(query_params)
                
                results = self.execute_dynamodb_query(query_params)
                
                if results is not None:
                    st.session_state.query_results = results
                    st.session_state.current_page = 1
                    st.session_state.expanded_articles = set()
                    
                    if query_input not in st.session_state.query_history:
                        st.session_state.query_history.append(query_input)
                    
                    st.success(f"✅ Query executed successfully! Found {len(results)} records.")
        
        if st.session_state.query_results is not None:
            st.markdown("---")
            self.display_results(st.session_state.query_results)


def main():
    try:
        app = InsuranceQueryApp()
        app.run()
    except Exception as e:
        st.error(f"❌ Application Error: {str(e)}")
        logger.error(f"Application error: {e}", exc_info=True)


if __name__ == "__main__":
    main()



















# import streamlit as st
# import pandas as pd
# from datetime import datetime
# import json
# from typing import Optional
# from dynamo import DynamoDBClient
# from query_generator import QueryGenerator
# from logger import get_logger
# from concern_risk_misc_naics import concerns_events, emerging_risks, misc_topics, naics_data

# logger = get_logger(__name__)

# # Page configuration
# st.set_page_config(
#     page_title="Emerging Insights Query System",
#     page_icon="📊",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# # Enhanced CSS for card-based layout
# st.markdown("""
# <style>
#     .main-header {
#         font-size: 2.5rem;
#         color: #1f77b4;
#         text-align: center;
#         margin-bottom: 1rem;
#         font-weight: bold;
#     }
#     .sub-header {
#         font-size: 1.2rem;
#         color: #555;
#         text-align: center;
#         margin-bottom: 2rem;
#     }
#     .stats-box {
#         background-color: #f0f2f6;
#         padding: 20px;
#         border-radius: 10px;
#         border-left: 5px solid #1f77b4;
#         margin: 10px 0;
#         height: 180px
#     }
#     .query-explanation {
#         background-color: #e8f4f8;
#         padding: 15px;
#         border-radius: 8px;
#         border-left: 4px solid #2196F3;
#         margin: 15px 0;
#         font-size: 0.9rem;
#     }
#     .article-card {
#         background: white;
#         border: 1px solid #e0e0e0;
#         border-radius: 12px;
#         padding: 20px;
#         margin-bottom: 20px;
#         box-shadow: 0 2px 8px rgba(0,0,0,0.1);
#         transition: all 0.3s ease;
#     }
#     .article-card:hover {
#         box-shadow: 0 4px 16px rgba(0,0,0,0.15);
#         transform: translateY(-2px);
#     }
#     .article-title {
#         font-size: 1.3rem;
#         font-weight: bold;
#         color: #1f77b4;
#         margin-bottom: 10px;
#         line-height: 1.4;
#     }
#     .article-summary {
#         color: #555;
#         font-size: 0.95rem;
#         line-height: 1.6;
#         margin-bottom: 15px;
#     }
#     .article-meta {
#         display: flex;
#         gap: 15px;
#         flex-wrap: wrap;
#         margin-bottom: 10px;
#         font-size: 0.85rem;
#     }
#     .meta-item {
#         background: #f5f5f5;
#         padding: 5px 10px;
#         border-radius: 5px;
#         color: #666;
#     }
#     .tag-current {
#         background-color: #4CAF50;
#         color: white;
#         padding: 5px 12px;
#         border-radius: 5px;
#         font-weight: bold;
#         display: inline-block;
#     }
#     .tag-trend {
#         background-color: #FF9800;
#         color: white;
#         padding: 5px 12px;
#         border-radius: 5px;
#         font-weight: bold;
#         display: inline-block;
#     }
#     .tag-untagged {
#         background-color: #9E9E9E;
#         color: white;
#         padding: 5px 12px;
#         border-radius: 5px;
#         font-weight: bold;
#         display: inline-block;
#     }
#     .tag-error {
#         background-color: #F44336;
#         color: white;
#         padding: 5px 12px;
#         border-radius: 5px;
#         font-weight: bold;
#         display: inline-block;
#     }
#     .expand-btn {
#         background-color: #1f77b4;
#         color: white;
#         border: none;
#         padding: 8px 16px;
#         border-radius: 5px;
#         cursor: pointer;
#         font-size: 0.9rem;
#         transition: background-color 0.3s;
#     }
#     .expand-btn:hover {
#         background-color: #155a8a;
#     }
#     .full-content {
#         background: #f9f9f9;
#         padding: 20px;
#         border-radius: 8px;
#         margin-top: 15px;
#         border-left: 4px solid #1f77b4;
#     }
#     .filter-section {
#         background: #f8f9fa;
#         padding: 20px;
#         border-radius: 10px;
#         margin-bottom: 20px;
#     }
#     .concern-badge {
#         background: #e3f2fd;
#         color: #1976d2;
#         padding: 4px 10px;
#         border-radius: 4px;
#         margin: 3px;
#         display: inline-block;
#         font-size: 0.85rem;
#     }
#     .risk-badge {
#         background: #fff3e0;
#         color: #f57c00;
#         padding: 4px 10px;
#         border-radius: 4px;
#         margin: 3px;
#         display: inline-block;
#         font-size: 0.85rem;
#     }
# </style>
# """, unsafe_allow_html=True)


# class InsuranceQueryApp:
#     def __init__(self):
#         self.initialize_session_state()
#         self.dynamo_client = DynamoDBClient()
#         self.query_generator = QueryGenerator()
    
#     def initialize_session_state(self):
#         """Initialize session state variables."""
#         if 'query_results' not in st.session_state:
#             st.session_state.query_results = None
#         if 'query_history' not in st.session_state:
#             st.session_state.query_history = []
#         if 'last_query' not in st.session_state:
#             st.session_state.last_query = ""
#         if 'expanded_articles' not in st.session_state:
#             st.session_state.expanded_articles = set()
    
#     def execute_dynamodb_query(self, query_params: dict) -> Optional[list]:
#         """Execute the DynamoDB query based on generated parameters."""
#         try:
#             table = self.dynamo_client.table
#             scan_kwargs = {}
            
#             if query_params.get("filter_expression"):
#                 scan_kwargs["FilterExpression"] = query_params["filter_expression"]
            
#             if query_params.get("expression_attribute_names") and query_params.get("filter_expression"):
#                 scan_kwargs["ExpressionAttributeNames"] = query_params["expression_attribute_names"]
            
#             if query_params.get("expression_attribute_values") and query_params.get("filter_expression"):
#                 attr_values = {}
#                 for key, value in query_params["expression_attribute_values"].items():
#                     attr_values[key] = value
#                 scan_kwargs["ExpressionAttributeValues"] = attr_values
            
#             if query_params.get("limit"):
#                 scan_kwargs["Limit"] = query_params["limit"]
            
#             if query_params["query_type"] == "query" and query_params.get("partition_key"):
#                 from boto3.dynamodb.conditions import Key
#                 pk = query_params["partition_key"]
#                 scan_kwargs["KeyConditionExpression"] = Key(pk["name"]).eq(pk["value"])
#                 response = table.query(**scan_kwargs)
#             else:
#                 response = table.scan(**scan_kwargs)
            
#             items = response.get('Items', [])
            
#             while 'LastEvaluatedKey' in response and len(items) < query_params.get("limit", 100):
#                 scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
#                 response = table.scan(**scan_kwargs)
#                 items.extend(response.get('Items', []))
            
#             logger.info(f"Query returned {len(items)} items")
#             return items
            
#         except Exception as e:
#             logger.error(f"Error executing DynamoDB query: {e}")
#             st.error(f"Error executing query: {str(e)}")
#             return None
    
#     def format_tag(self, tag: str) -> str:
#         """Format tag with appropriate styling."""
#         if not tag:
#             return '<span class="tag-untagged">Untagged</span>'
        
#         tag_classes = {
#             "Current": "tag-current",
#             "Potential New Trend": "tag-trend",
#             "Untagged": "tag-untagged",
#             "Processing Error": "tag-error"
#         }
        
#         css_class = tag_classes.get(tag, "tag-untagged")
#         return f'<span class="{css_class}">{tag}</span>'
    

#     def render_article_card(self, article: dict, index: int):
#         """Render individual article card with expand/collapse functionality."""
#         article_id = f"article_{index}"
#         is_expanded = article_id in st.session_state.expanded_articles
        
#         # Extract article data
#         # title = article.get('Title', 'Untitled Article')[:200]
#         title = article.get('Title') or 'Untitled Article'
#         title = str(title)[:200]
#         summary = article.get('ReasonIdentified', article.get('Description', 'No summary available'))[:300]
#         source = article.get('Source', 'Unknown Source')
#         tag = article.get('Tag', 'Untagged')
#         url = article.get('URL', '#')
#         concerns = article.get('Concerns', '').split(';') if article.get('Concerns') else []
#         risks = article.get('EmergingRiskName', '').split(';') if article.get('EmergingRiskName') else []
#         date_time = article.get('DateTime', 'Unknown Date')
        
#         # Build badges HTML
#         badges_html = ""
#         if concerns and concerns[0]:
#             badges_html += "<div style='margin-top: 10px;'>"
#             for concern in concerns[:5]:  # Show max 5
#                 if concern.strip():
#                     badges_html += f'<span class="concern-badge">🚨 {concern.strip()}</span>'
#             badges_html += "</div>"
        
#         if risks and risks[0]:
#             badges_html += "<div style='margin-top: 5px;'>"
#             for risk in risks[:5]:  # Show max 5
#                 if risk.strip():
#                     badges_html += f'<span class="risk-badge">⚠️ {risk.strip()}</span>'
#             badges_html += "</div>"
        
#         # Create card HTML with badges inside
#         st.markdown(f"""
#         <div class="article-card">
#             <div class="article-title">{title}</div>
#             <div class="article-meta">
#                 <span class="meta-item">📅 {date_time[:10] if date_time != 'Unknown Date' else date_time}</span>
#                 <span class="meta-item">📰 {source}</span>
#                 <span>{self.format_tag(tag)}</span>
#             </div>
#             <div class="article-summary">{summary}{'...' if len(summary) >= 300 else ''}</div>
#             {badges_html}
#         """, unsafe_allow_html=True)
        
#         # Expand/Collapse button
#         col1, col2, col3 = st.columns([1, 1, 4])
#         with col1:
#             if st.button("Read Full Article" if not is_expanded else "📕 Collapse", key=f"expand_{article_id}"):
#                 if is_expanded:
#                     st.session_state.expanded_articles.remove(article_id)
#                 else:
#                     st.session_state.expanded_articles.add(article_id)
#                 st.rerun()
        
#         with col2:
#             if url and url != '#':
#                 st.markdown(f'<a href="{url}" target="_blank" style="text-decoration: none;"><button class="expand-btn">🔗 Source</button></a>', unsafe_allow_html=True)
        
#         # Show full content if expanded
#         if is_expanded:
#             st.markdown('<div class="full-content">', unsafe_allow_html=True)
            
#             # Full details
#             st.markdown("### 📄 Full Article Content")
#             full_data = article.get('Data', 'No full content available')
#             st.text_area("", value=full_data, height=300, key=f"content_{article_id}")
            
#             # Additional metadata
#             st.markdown("### 📊 Classification Details")
#             col1, col2 = st.columns(2)
            
#             with col1:
#                 if concerns and concerns[0]:
#                     st.markdown("**Concerns:**")
#                     for concern in concerns:
#                         if concern.strip():
#                             st.write(f"• {concern.strip()}")
                
#                 if article.get('MiscTopics'):
#                     topics = article.get('MiscTopics', '').split(';')
#                     st.markdown("**Misc Topics:**")
#                     for topic in topics:
#                         if topic.strip():
#                             st.write(f"• {topic.strip()}")
            
#             with col2:
#                 if risks and risks[0]:
#                     st.markdown("**Emerging Risks:**")
#                     for risk in risks:
#                         if risk.strip():
#                             st.write(f"• {risk.strip()}")
                
#                 if article.get('NAICSCODE'):
#                     st.markdown("**NAICS:**")
#                     st.write(f"• Code: {article.get('NAICSCODE')}")
#                     st.write(f"• {article.get('NAICSDescription', 'N/A')}")
            
#             st.markdown('</div>', unsafe_allow_html=True)
        
#         st.markdown("</div>", unsafe_allow_html=True)
    
#     def display_results(self, results: list):
#         """Display query results in card format."""
#         if not results:
#             st.warning("No results found for your query.")
#             return
        
#         df = pd.DataFrame(results)
        
#         # Display statistics
#         col1, col2, col3, col4 = st.columns(4)
        
#         with col1:
#             st.markdown(f"""
#             <div class="stats-box">
#                 <h2 style="margin:0; color:#1f77b4; height:100px">Total Records</h2>
#                 <h3> {len(df)} </h3>
#             </div>
#             """, unsafe_allow_html=True)
        
#         with col2:
#             current_count = len(df[df.get('Tag', '') == 'Current']) if 'Tag' in df.columns else 0
#             st.markdown(f"""
#             <div class="stats-box">
#                 <h2 style="margin:0; color:#4CAF50; height:100px">Current</h2>
#                 <h3> {current_count} </h3>
#             </div>
#             """, unsafe_allow_html=True)
        
#         with col3:
#             trend_count = len(df[df.get('Tag', '') == 'Potential New Trend']) if 'Tag' in df.columns else 0
#             st.markdown(f"""
#             <div class="stats-box">
#                 <h2 style="margin:0; color:#FF9800; height:100px">New Trends</h2>
#                 <h3> {trend_count} </h3>
#             </div>
#             """, unsafe_allow_html=True)
        
#         with col4:
#             untagged_count = len(df[df.get('Tag', '').isin(['Untagged', '', None])]) if 'Tag' in df.columns else 0
#             st.markdown(f"""
#             <div class="stats-box">
#                 <h2 style="margin:0; color:#9E9E9E; height:100px">Untagged</h2>
#                 <h3> {untagged_count} </h3>
#             </div>
#             """, unsafe_allow_html=True)
        
#         st.markdown("---")
        
#         # Filters
#         st.markdown('<div class="filter-section">', unsafe_allow_html=True)
#         st.markdown("### Filter Results")
        
#         filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
        
#         with filter_col1:
#             if 'Tag' in df.columns:
#                 tag_filter = st.multiselect(
#                     "Filter by Tag:",
#                     options=df['Tag'].unique().tolist(),
#                     key="tag_filter"
#                 )
#                 if tag_filter:
#                     df = df[df['Tag'].isin(tag_filter)]
        
#         with filter_col2:
#             if 'Source' in df.columns:
#                 source_filter = st.multiselect(
#                     "Filter by Source:",
#                     options=df['Source'].dropna().unique().tolist(),
#                     key="source_filter"
#                 )
#                 if source_filter:
#                     df = df[df['Source'].isin(source_filter)]
        
#         with filter_col3:
#             sort_by = st.selectbox(
#                 "Sort by:",
#                 options=["Most Recent", "Title A-Z", "Source"],
#                 key="sort_option"
#             )
        
#         with filter_col4:
#             items_per_page = st.selectbox(
#                 "Items per page:",
#                 options=[10, 20, 50, 100],
#                 index=1,
#                 key="items_per_page"
#             )
        
#         st.markdown('</div>', unsafe_allow_html=True)
        
#         # Apply sorting
#         if sort_by == "Most Recent" and 'DateTime' in df.columns:
#             df = df.sort_values('DateTime', ascending=False)
#         elif sort_by == "Title A-Z" and 'Title' in df.columns:
#             df = df.sort_values('Title')
#         elif sort_by == "Source" and 'Source' in df.columns:
#             df = df.sort_values('Source')
        
#         # Pagination
#         total_items = len(df)
#         total_pages = (total_items + items_per_page - 1) // items_per_page
        
#         if 'current_page' not in st.session_state:
#             st.session_state.current_page = 1
        
#         # Display articles
#         st.markdown(f"### 📋 Showing {min(items_per_page, total_items)} of {total_items} articles")
        
#         start_idx = (st.session_state.current_page - 1) * items_per_page
#         end_idx = min(start_idx + items_per_page, total_items)
        
#         # Render article cards
#         for idx in range(start_idx, end_idx):
#             self.render_article_card(df.iloc[idx].to_dict(), idx)
        
#         # Pagination controls
#         if total_pages > 1:
#             st.markdown("---")
#             col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            
#             with col1:
#                 if st.button("⏮️ First", disabled=st.session_state.current_page == 1):
#                     st.session_state.current_page = 1
#                     st.rerun()
            
#             with col2:
#                 if st.button("◀️ Previous", disabled=st.session_state.current_page == 1):
#                     st.session_state.current_page -= 1
#                     st.rerun()
            
#             with col3:
#                 st.markdown(f"<p style='text-align: center;'>Page {st.session_state.current_page} of {total_pages}</p>", unsafe_allow_html=True)
            
#             with col4:
#                 if st.button("Next ▶️", disabled=st.session_state.current_page == total_pages):
#                     st.session_state.current_page += 1
#                     st.rerun()
            
#             with col5:
#                 if st.button("Last ⏭️", disabled=st.session_state.current_page == total_pages):
#                     st.session_state.current_page = total_pages
#                     st.rerun()
        
#         # Download options
#         st.markdown("---")
#         st.markdown("### 💾 Export Data")
#         col1, col2 = st.columns(2)
        
#         with col1:
#             csv = df.to_csv(index=False)
#             st.download_button(
#                 label="📥 Download as CSV",
#                 data=csv,
#                 file_name=f"insurance_query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
#                 mime="text/csv"
#             )
        
#         with col2:
#             json_str = df.to_json(orient='records', indent=2)
#             st.download_button(
#                 label="📥 Download as JSON",
#                 data=json_str,
#                 file_name=f"insurance_query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
#                 mime="application/json"
#             )
    
#     def render_sidebar(self):
#         """Render sidebar with query examples and reference data."""
#         st.sidebar.title("Query Assistant")
        
#         st.sidebar.markdown("### 📊 Example Queries")
        
#         if st.sidebar.button("📊 Show All Articles", key="show_all", type="primary"):
#             st.session_state.last_query = "show all articles"
#             st.session_state.current_page = 1
#             st.rerun()
        
#         st.sidebar.markdown("---")
#         st.sidebar.markdown("**FAQs:**")
        
#         examples = [
#             "Show all articles tagged as Current",
#             "Find articles about Climate Change",
#             "Show articles with lawsuits or property damage concerns",
#             "Find Potential New Trend articles about PFAS",
#             "Show articles from Construction Industry",
#             "Find articles about ransomware and cyber attacks",
#             "Show untagged articles",
#             "Find articles about electric vehicles",
#             "Show articles with NAICS code 524126"
#         ]
        
#         for i, example in enumerate(examples):
#             if st.sidebar.button(example, key=f"example_{i}"):
#                 st.session_state.last_query = example
#                 st.session_state.current_page = 1
#                 st.rerun()
        
#         st.sidebar.markdown("---")
#         st.sidebar.markdown("### 📚 Reference Data")
        
#         with st.sidebar.expander("🚨 Concerns Available"):
#             st.write(", ".join(concerns_events[:20]) + "...")
            
#         with st.sidebar.expander("⚠️ Emerging Risks Available"):
#             st.write(", ".join(emerging_risks[:20]) + "...")
        
#         with st.sidebar.expander("📌 Misc Topics Available"):
#             st.write(", ".join(misc_topics))
        
#         with st.sidebar.expander("🏭 NAICS Codes"):
#             st.write(f"Total codes available: {len(naics_data)}")
#             st.write("Sample:", ", ".join([f"{n['code']}" for n in naics_data[:5]]) + "...")
    
#     def run(self):
#         """Main application loop."""
#         st.markdown('<h1 class="main-header"> Emerging Insights Query System</h1>', unsafe_allow_html=True)
#         st.markdown('<p class="sub-header">Search and analyze insurance-related articles using natural language queries</p>', unsafe_allow_html=True)
        
#         self.render_sidebar()
        
#         st.markdown("### Enter Your Query")
        
#         query_input = st.text_area(
#             "Describe what you're looking for:",
#             value=st.session_state.last_query,
#             height=100,
#             placeholder="Example: Show me all articles about climate change with property damage concerns..."
#         )
        
#         col1, col2, col3 = st.columns([1, 1, 3])
        
#         with col1:
#             search_button = st.button("🔎 Search", type="primary")
        
#         with col2:
#             clear_button = st.button("🗑️ Clear")
        
#         if clear_button:
#             st.session_state.last_query = ""
#             st.session_state.query_results = None
#             st.session_state.current_page = 1
#             st.session_state.expanded_articles = set()
#             st.rerun()
        
#         if search_button and query_input.strip():
#             with st.spinner("🤖 Generating and executing query..."):
#                 query_params = self.query_generator.generate_query(query_input)
                
#                 if query_params.get("explanation"):
#                     st.markdown(f"""
#                     <div class="query-explanation">
#                         <strong>🎯 Query Understanding:</strong> {query_params['explanation']}
#                     </div>
#                     """, unsafe_allow_html=True)
                
#                 with st.expander("🔧 Technical Query Details"):
#                     st.json(query_params)
                
#                 results = self.execute_dynamodb_query(query_params)
                
#                 if results is not None:
#                     st.session_state.query_results = results
#                     st.session_state.current_page = 1
#                     st.session_state.expanded_articles = set()
                    
#                     if query_input not in st.session_state.query_history:
#                         st.session_state.query_history.append(query_input)
                    
#                     st.success(f"✅ Query executed successfully! Found {len(results)} records.")
        
#         if st.session_state.query_results is not None:
#             st.markdown("---")
#             self.display_results(st.session_state.query_results)


# def main():
#     try:
#         app = InsuranceQueryApp()
#         app.run()
#     except Exception as e:
#         st.error(f"❌ Application Error: {str(e)}")
#         logger.error(f"Application error: {e}", exc_info=True)


# if __name__ == "__main__":
#     main()

