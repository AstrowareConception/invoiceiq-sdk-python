from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class Address(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    postCode: Optional[str] = None
    city: Optional[str] = None
    countryCode: Optional[str] = None


class Party(BaseModel):
    name: str
    registrationId: Optional[str] = None
    vatId: Optional[str] = None
    countryCode: Optional[str] = None
    address: Optional[Address] = None


class LogoOptions(BaseModel):
    url: Optional[str] = None
    width: Optional[int] = None
    align: Optional[str] = Field(default=None, pattern=r"^(left|center|right)$")


class FooterOptions(BaseModel):
    extraText: Optional[str] = None
    showPageNumbers: Optional[bool] = None


class RenderingOptions(BaseModel):
    template: Optional[str] = None
    font: Optional[str] = None
    primaryColor: Optional[str] = None
    accentColor: Optional[str] = None
    logo: Optional[LogoOptions] = None
    footer: Optional[FooterOptions] = None
    notes: Optional[str] = None
    locale: Optional[str] = None


class InvoiceLine(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    quantity: float
    unitCode: Optional[str] = Field(default="C62")
    netPrice: Optional[float] = None
    unitPrice: Optional[float] = None  # certains exemples utilisent unitPrice
    taxRate: Optional[float] = None
    taxCategoryCode: Optional[str] = Field(default="S")
    taxExemptionReason: Optional[str] = None
    totalAmount: float


class TaxSummary(BaseModel):
    taxRate: Optional[float] = None
    basisAmount: Optional[float] = None
    taxableAmount: Optional[float] = None
    taxAmount: Optional[float] = None
    taxCategoryCode: Optional[str] = Field(default="S")
    taxExemptionReason: Optional[str] = None


class TransformationMetadata(BaseModel):
    invoiceNumber: str
    issueDate: str
    currency: Optional[str] = Field(default="EUR")
    typeCode: Optional[str] = Field(default="380")
    seller: Party
    buyer: Party
    lines: Optional[List[InvoiceLine]] = None
    taxes: Optional[List[TaxSummary]] = None
    taxSummaries: Optional[List[TaxSummary]] = None
    totalTaxExclusiveAmount: float
    taxTotalAmount: float
    totalTaxInclusiveAmount: float
    purchaseOrderReference: Optional[str] = None
    rendering: Optional[RenderingOptions] = None


class GenerationPayload(TransformationMetadata):
    pass


class Job(BaseModel):
    id: str
    status: str
    downloadUrl: Optional[str] = None
    reportDownloadUrl: Optional[str] = None


class ValidationReport(BaseModel):
    transformation: Optional[str] = None
    finalScore: Optional[float] = None
    profile: Optional[str] = None
    issues: Optional[list] = None
