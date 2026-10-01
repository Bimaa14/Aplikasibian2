<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class TransactionDetail extends Model
{
    protected $fillable = ['transaction_id', 'product_id', 'qty', 'price', 'cost_price', 'service_fee', 'subtotal'];

    protected $casts = [
        'qty' => 'integer',
        'price' => 'float',
        'cost_price' => 'float',
        'service_fee' => 'float',
        'subtotal' => 'float',
    ];

    public function product()
    {
        return $this->belongsTo(Product::class);
    }

    public function transaction()
    {
        return $this->belongsTo(Transaction::class);
    }

    /** Laba baris ini: barang = (jual - modal) × qty, jasa = (jual - komisi montir) × qty */
    public function profit(): float
    {
        return $this->product->isService()
            ? ($this->price - $this->service_fee) * $this->qty
            : ($this->price - $this->cost_price) * $this->qty;
    }
}
