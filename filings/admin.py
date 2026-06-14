from django.contrib import admin

from .models import Company, Filing, FilingChunk, FilingItem


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("ticker", "name", "cik", "exchange")
    search_fields = ("ticker", "name", "cik")


class FilingItemInline(admin.TabularInline):
    model = FilingItem
    fields = ("item_code", "title", "confidence", "warnings")
    readonly_fields = ("item_code", "title", "confidence", "warnings")
    extra = 0


class FilingChunkInline(admin.TabularInline):
    model = FilingChunk
    fields = ("item_code", "chunk_index", "embedding_model", "embedding_error")
    readonly_fields = ("item_code", "chunk_index", "embedding_model", "embedding_error")
    extra = 0


@admin.register(Filing)
class FilingAdmin(admin.ModelAdmin):
    list_display = ("company", "form_type", "filing_date", "fiscal_year", "status")
    list_filter = ("form_type", "status", "filing_date")
    search_fields = ("accession_number", "company__ticker", "company__name")
    inlines = [FilingItemInline, FilingChunkInline]


@admin.register(FilingChunk)
class FilingChunkAdmin(admin.ModelAdmin):
    list_display = ("filing", "item_code", "chunk_index", "embedding_model")
    list_filter = ("item_code", "embedding_model")
    search_fields = ("text", "filing__company__ticker", "filing__accession_number")
